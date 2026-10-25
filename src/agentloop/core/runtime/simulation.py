"""仅写本地记录的部署模拟器；不提供网络或服务器执行能力。"""

from uuid import uuid4

from ..contracts.enums import ActorType, DeploymentStatus, EventType, ReleaseAction, RunPhase, RunStatus, ToolExecutionStatus
from ..contracts.models import Deployment, ToolExecution, utc_now
from ..orchestration.store import atomic


class SimulatedDeployment:
    def __init__(self, store, transitions, rbac):
        self.store, self.transitions, self.rbac = store, transitions, rbac

    def validate_authorization(self, run_id, authorization_id):
        mode=self.store.runtime_get("workflow_mode",run_id)
        if mode and mode["mode"]=="phase3":raise PermissionError("真实发布 Run 不能切换为模拟发布")
        run = self.store.get_run(run_id)
        authorization = self.store.get_authorization(authorization_id)
        release = self.store.get_release(authorization.release_id)
        self.rbac.require_human(authorization.issued_by)
        if "release_approver" not in self.rbac.roles_of(authorization.issued_by, run.project_id):
            raise PermissionError("模拟发布仍需有效真人发布角色")
        if (release.run_id != run_id or authorization.project_id != run.project_id
                or authorization.commit_sha != run.baseline_versions["commit"]
                or release.commit_sha != authorization.commit_sha
                or release.spec_digest != run.baseline_versions.get("spec")
                or release.architecture_digest != run.baseline_versions.get("architecture")):
            raise ValueError("模拟发布与当前 Run/Commit 不匹配")
        allowed, reason = authorization.is_valid_for(utc_now(), release.release_id, "simulation", "local-simulator",
                                                     release.artifact_digest, ReleaseAction.DEPLOY)
        if not allowed:
            raise PermissionError(reason)
        self.transitions.require_fresh_passing_gate(run_id, "G1")
        gate = self.transitions.require_fresh_passing_gate(run_id, "G2")
        if gate.gate_result_id != release.g2_gate_result_id:
            raise ValueError("模拟发布许可绑定的 G2 已被替换")
        return authorization

    @atomic
    def execute(self, run_id, authorization_id):
        key = f"{run_id}:SIMULATE:{authorization_id}"
        previous = self.store.find_tool_execution_by_key(key)
        if previous is not None:
            if previous.status is not ToolExecutionStatus.SUCCEEDED:
                raise ValueError("模拟操作未结算，不能重复执行")
            return self.store.get_deployment(previous.external_operation_id)
        authorization = self.validate_authorization(run_id, authorization_id)
        deployment = Deployment(deployment_id="simulation-" + uuid4().hex, release_id=authorization.release_id,
            run_id=run_id, attempt_no=len(self.store.deployments_for(run_id)) + 1, environment_id="simulation",
            target_ids=["local-simulator"], release_artifact_digest=authorization.artifact_digest,
            authorization_id=authorization_id)
        self.store.put_deployment(deployment)
        run = self.store.get_run(run_id)
        self.transitions.transition(run_id, target_phase=RunPhase.DEPLOYMENT, target_status=RunStatus.RUNNING,
                                    expected_version=run.state_version)
        authorization.consume()
        self.store.put_authorization(authorization)
        deployment.status = DeploymentStatus.SUCCEEDED
        self.store.put_deployment(deployment)
        self.store.put_tool_execution(ToolExecution(invocation_id=key, run_id=run_id, task_id="simulation",
            tool_name="local-simulator", params_hash=authorization_id, idempotency_key=key,
            status=ToolExecutionStatus.SUCCEEDED, external_operation_id=deployment.deployment_id, settled_at=utc_now()))
        self.store.append_event(run_id=run_id, event_type=EventType.DEPLOYMENT_RESULT_RECORDED,
            actor_id="local-simulator", actor_type=ActorType.SYSTEM, payload_ref=deployment.model_dump_json(), idempotency_key=key)
        return deployment
