"""独立 SideEffectExecutor：先持久租约和操作 ID，再发送不可盲重放的外部写入。"""

from datetime import timedelta
from uuid import uuid4
from urllib.parse import urlparse
from ..approvals import AccessDenied, RBACService
from ..contracts.enums import (ActorType, AuthorizationStatus, DeploymentStatus, EventType,
    PrincipalType, ReleaseAction, ReleaseStatus, RunPhase, RunStatus, ToolExecutionStatus)
from ..contracts.models import Deployment, ToolExecution, utc_now
from ..contracts.phase3 import DeploymentTarget, ExecutionPolicy, DeploymentObservation
from ..orchestration import StateTransitionService, TransitionRejected
from .configuration import digest
from .deployment_providers import validate_bundle


class EffectUncertain(ValueError): pass


class SideEffectExecutor:
    def __init__(self, repository, *, service_principal, providers, clock=utc_now, production_enabled=False):
        self.repo, self.store, self.clock = repository, repository.store, clock
        self.rbac = RBACService(self.store)
        self.service_principal, self.providers = service_principal, providers
        self.production_enabled = production_enabled
        self.transitions = StateTransitionService(self.store, deployment_guard=self._guard_entry)

    def register_target(self, target, *, principal_id):
        self.rbac.require_human(principal_id)
        self.rbac.require_role(principal_id, "project_owner", target.project_id)
        body = target.model_dump(mode="json")
        with self.store.transaction():
            key=f"{target.project_id}/{target.target_id}"
            old=self.store.runtime_get("deployment_target",key)
            lease=self.store.runtime_get("target_lease",key)
            if old and old["digest"]!=digest(body) and lease and lease["active"]:
                raise PermissionError("目标仍有部署/恢复租约，不能替换目标配置")
            self.store.runtime_put("deployment_target", key, {"digest": digest(body), "config": body})

    def bind_policy(self, run_id, policy, *, principal_id):
        run = self.store.get_run(run_id)
        self.rbac.require_human(principal_id)
        self.rbac.require_role(principal_id, "project_owner", run.project_id)
        self.rbac.assert_project_access(policy.principal_id, run.project_id)
        key = f"{run_id}/{policy.principal_id}"
        body = policy.model_dump(mode="json")
        with self.store.transaction():
            old = self.store.runtime_get("execution_policy", key)
            if old and old != body: raise ValueError("执行能力快照不可原位更换")
            self.store.runtime_put("execution_policy", key, body)
            self.repo.audit(run_id, "EXECUTION_POLICY_BOUND", {"principal_id": policy.principal_id, "digest": digest(body)})

    def target(self, project, target_id):
        record = self.store.runtime_get("deployment_target", f"{project}/{target_id}")
        if not record: raise ValueError("部署目标未登记")
        target = DeploymentTarget.model_validate(record["config"])
        if digest(target.model_dump(mode="json")) != record["digest"]: raise ValueError("部署目标配置损坏")
        return target, record["digest"]

    def _identity(self, run_id, actor_id):
        run = self.store.get_run(run_id)
        self.rbac.assert_project_access(actor_id, run.project_id)
        principal = self.rbac.get_principal(self.service_principal)
        if principal.principal_type is not PrincipalType.SYSTEM_SERVICE or actor_id == self.service_principal:
            raise PermissionError("执行器必须使用独立 system_service 身份")
        self.rbac.require_role(self.service_principal, "side_effect_executor", run.project_id)
        body = self.store.runtime_get("execution_policy", f"{run_id}/{actor_id}")
        if not body: raise PermissionError("缺少运行绑定的执行能力快照")
        return ExecutionPolicy.model_validate(body)

    def _validate(self, run_id, actor_id, authorization_id, target_id, *, rollback=False, allow_consumed=False):
        run = self.store.get_run(run_id)
        policy = self._identity(run_id, actor_id)
        target, target_digest = self.target(run.project_id, target_id)
        if target.environment == "production" and not self.production_enabled:
            raise PermissionError("生产执行默认关闭，必须由受信宿主显式启用")
        if f"cap.deploy.{target.environment}" not in policy.grants() or target_id not in policy.target_ids:
            raise PermissionError("部署 Capability 或目标交集拒绝")
        if target.provider == "http-agent" and (urlparse(target.endpoint).hostname not in policy.network_hosts or target.secret_ref not in policy.secrets):
            raise PermissionError("部署代理网络/凭据未授权")
        authorization = self.store.get_authorization(authorization_id)
        release = self.store.get_release(authorization.release_id)
        self.rbac.require_human(authorization.issued_by)
        if "release_approver" not in self.rbac.roles_of(authorization.issued_by, run.project_id, self.clock()):
            raise PermissionError("签发人的发布审批角色已失效")
        if (release.run_id != run_id or authorization.project_id != run.project_id
                or authorization.commit_sha != release.commit_sha
                or release.commit_sha != run.baseline_versions.get("commit")
                or release.spec_digest != run.baseline_versions.get("spec")
                or release.architecture_digest != run.baseline_versions.get("architecture")
                or authorization.artifact_digest != release.artifact_digest):
            raise PermissionError("发布许可与当前基线/产物不匹配")
        bound = self.store.runtime_get("authorization_targets", authorization_id) or {}
        if set(authorization.target_ids) != {target_id}: raise PermissionError("本执行器要求精确的单目标授权")
        if bound.get(target_id) != target_digest: raise PermissionError("许可未绑定当前目标配置")
        candidate = authorization.model_copy(deep=True)
        if allow_consumed and candidate.status is AuthorizationStatus.EXHAUSTED:
            candidate.status, candidate.uses = AuthorizationStatus.ACTIVE, 0
        allowed, reason = candidate.is_valid_for(self.clock(), release.release_id, target.environment, target_id,
            release.artifact_digest, ReleaseAction.ROLLBACK if rollback else ReleaseAction.DEPLOY)
        if not allowed: raise PermissionError(reason)
        if not rollback:
            if not allow_consumed and release.status is not ReleaseStatus.READY: raise PermissionError("Release 不处于可发布状态")
            self.transitions.require_fresh_passing_gate(run_id, "G1", now=self.clock())
            gate = self.transitions.require_fresh_passing_gate(run_id, "G2", now=self.clock())
            if release.g2_gate_result_id != gate.gate_result_id: raise PermissionError("Release 的 G2 已失效")
        return authorization, release, target

    def _guard_entry(self, run_id):
        effects = [e for e in self.store.runtime_list("effect") if e["run_id"] == run_id and e["state"] == "PREPARED" and e["action"] == "DEPLOY"]
        if len(effects) != 1: raise PermissionError("部署入口需要唯一已准备的执行器凭据")
        effect = effects[0]
        self._validate(run_id, effect["actor_id"], effect["authorization_id"], effect["target_id"], allow_consumed=True)
        if not self.store.find_tool_execution_by_key(effect["idempotency_key"]): raise PermissionError("缺少持久操作凭据")

    def execute(self, *, run_id, actor_id, authorization_id, target_id, bundle, idempotency_key):
        key = digest({"run": run_id, "key": idempotency_key})
        with self.store.transaction():
            self._identity(run_id, actor_id)
            old = self.store.runtime_get("effect", key)
            if old:
                if (old["actor_id"], old["authorization_id"], old["target_id"], old["params_hash"]) != (actor_id, authorization_id, target_id, digest(bundle)):
                    raise ValueError("副作用幂等键冲突")
                if old["state"] == "SUCCEEDED": return self.store.get_deployment(old["deployment_id"])
                raise EffectUncertain("已有未结算外部操作，只允许查询对账")
            run = self.store.get_run(run_id)
            if run.phase is not RunPhase.RELEASE_AUTHORIZATION or run.status not in {RunStatus.RUNNING, RunStatus.WAITING_APPROVAL}:
                raise PermissionError("仅就绪的发布授权阶段可以启动部署")
            if self.store.pending_tool_executions(run_id): raise EffectUncertain("存在未结算操作")
            auth, release, target = self._validate(run_id, actor_id, authorization_id, target_id)
            validate_bundle(bundle, release.artifact_digest)
            if bundle["commit"] != release.commit_sha: raise PermissionError("部署包源 Commit 与 Release 不匹配")
            lease_key = f"{run.project_id}/{target_id}"
            lease = self.store.runtime_get("target_lease", lease_key)
            if lease and lease["active"]: raise EffectUncertain("目标租约未释放，须先核对已有部署")
            deployment = Deployment(deployment_id="deployment-" + uuid4().hex, release_id=release.release_id,
                run_id=run_id, attempt_no=len(self.store.deployments_for(run_id)) + 1, environment_id=target.environment,
                target_ids=[target_id], release_artifact_digest=release.artifact_digest, authorization_id=authorization_id)
            effect = {"id": key, "idempotency_key": key, "run_id": run_id, "actor_id": actor_id,
                "authorization_id": authorization_id, "target_id": target_id, "deployment_id": deployment.deployment_id,
                "operation_id": "op-" + uuid4().hex, "action": "DEPLOY", "state": "PREPARED", "params_hash": digest(bundle),
                "lease_until": (self.clock() + timedelta(minutes=5)).isoformat(), "previous_digest": None,"dispatched":False}
            self.store.runtime_put("effect", key, effect)
            self.store.runtime_put("target_lease", lease_key, {"active": True, "deployment_id": deployment.deployment_id})
            self.store.put_deployment(deployment)
            self.store.put_tool_execution(ToolExecution(invocation_id=key, run_id=run_id, task_id=deployment.deployment_id,
                tool_name="deploy", params_hash=effect["params_hash"], idempotency_key=key, external_operation_id=effect["operation_id"]))
            auth.consume(); self.store.put_authorization(auth)
            release.status=ReleaseStatus.DEPLOYING; self.store.put_release(release)
            self.transitions.transition(run_id, target_phase=RunPhase.DEPLOYMENT, target_status=RunStatus.RUNNING, expected_version=run.state_version)
            deployment.status = DeploymentStatus.IN_PROGRESS; self.store.put_deployment(deployment)
            self.repo.audit(run_id, "SIDE_EFFECT_PREPARED", effect)
        cancelled=False
        cancel_reason=None
        with self.store.transaction():
            current_run=self.store.get_run(run_id)
            effect=self.store.runtime_get("effect",key)
            if current_run.status in {RunStatus.CANCEL_REQUESTED,RunStatus.CANCELLING,RunStatus.CANCELLED,RunStatus.NEEDS_RECONCILIATION}:
                cancel_reason="run_cancelling"
            else:
                # prepare 与 dispatch 之间复查许可/门禁/签发人：撤销在窗口内同样生效。
                try:
                    self._validate(run_id, actor_id, authorization_id, target_id, allow_consumed=True)
                except (PermissionError, AccessDenied, TransitionRejected):
                    cancel_reason="authorization_invalidated_before_dispatch"
            if cancel_reason:
                effect["state"]="CANCELLED";self.store.runtime_put("effect",key,effect)
                receipt=self.store.find_tool_execution_by_key(key);receipt.status=ToolExecutionStatus.CANCELLED;receipt.settled_at=self.clock();self.store.put_tool_execution(receipt)
                deployment.status=DeploymentStatus.FAILED;deployment.reconcile_state="CANCELLED_BEFORE_DISPATCH";self.store.put_deployment(deployment)
                release.status=ReleaseStatus.READY;self.store.put_release(release)
                self.release_lease(deployment)
                self.repo.audit(run_id,"SIDE_EFFECT_CANCELLED_BEFORE_DISPATCH",{"effect_id":key,"reason":cancel_reason})
                cancelled=True
            else:
                effect.update(dispatched=True,state="DISPATCHING");self.store.runtime_put("effect",key,effect)
        if cancelled:raise EffectUncertain("取消或许可失效已阻断尚未发送的外部请求")
        try:
            observation = self.providers[target_id].execute(effect["operation_id"], "DEPLOY", bundle=bundle, artifact_digest=release.artifact_digest)
        except Exception:
            self._unknown(effect, "deployment_transport_unknown")
            raise EffectUncertain("部署结果未知；已保留操作 ID，禁止重发") from None
        return self._settle(effect, observation)

    def _settle(self, effect, observation):
        observation = DeploymentObservation.model_validate(observation)
        if observation.operation_id != effect["operation_id"] or observation.status not in {"SUCCEEDED", "FAILED", "CANCELLED"}:
            self._unknown(effect, "operation_identity_or_state_unknown")
            raise EffectUncertain("操作身份或状态不确定")
        deployment = self.store.get_deployment(effect["deployment_id"])
        expected = deployment.release_artifact_digest if effect["action"] == "DEPLOY" else effect["previous_digest"]
        if (observation.status == "SUCCEEDED" and observation.artifact_digest != expected) or (effect["action"] == "ROLLBACK" and observation.status != "SUCCEEDED"):
            self._unknown(effect, "provider_artifact_or_rollback_unconfirmed")
            raise EffectUncertain("提供方产物或回滚结果未确认")
        with self.store.transaction():
            deployment = self.store.get_deployment(effect["deployment_id"])
            stored=self.store.runtime_get("effect",effect["id"])
            if stored and stored["state"] in {"SUCCEEDED","FAILED","CANCELLED"}:
                previous=stored.get("observation")
                if previous and (previous["operation_id"],previous["status"],previous.get("artifact_digest")) == (observation.operation_id,observation.status,observation.artifact_digest):
                    return deployment
                raise EffectUncertain("外部终态观察矛盾，不能覆盖已结算结果")
            effect.update(state=observation.status, previous_digest=observation.previous_digest,
                observation=observation.model_dump(mode="json"))
            self.store.runtime_put("effect", effect["id"], effect)
            receipt = self.store.find_tool_execution_by_key(effect["idempotency_key"])
            receipt.status = ToolExecutionStatus.SUCCEEDED if observation.status == "SUCCEEDED" else ToolExecutionStatus.FAILED
            receipt.settled_at = self.clock(); self.store.put_tool_execution(receipt)
            if effect["action"] == "DEPLOY":
                deployment.status = DeploymentStatus.SUCCEEDED if observation.status == "SUCCEEDED" else DeploymentStatus.FAILED
                deployment.external_operation_id = observation.operation_id
            else:
                deployment.status = DeploymentStatus.ROLLED_BACK if observation.status == "SUCCEEDED" else DeploymentStatus.UNKNOWN
                deployment.rollback_operation_id = observation.operation_id
            self.store.put_deployment(deployment)
            self.repo.audit(effect["run_id"], "SIDE_EFFECT_SETTLED", {"effect_id": effect["id"], "observation": observation.model_dump(mode="json")})
            return deployment

    def _unknown(self, effect, reason, *, force=False):
        with self.store.transaction():
            stored=self.store.runtime_get("effect",effect["id"])
            if not force and stored and stored["state"] in {"SUCCEEDED","FAILED","CANCELLED"}:
                self.repo.audit(effect["run_id"],"LATE_TRANSPORT_ERROR_IGNORED",{"effect_id":effect["id"],"reason":reason})
                return
            effect["state"] = "UNKNOWN"; self.store.runtime_put("effect", effect["id"], effect)
            receipt = self.store.find_tool_execution_by_key(effect["idempotency_key"])
            receipt.status = ToolExecutionStatus.UNKNOWN; self.store.put_tool_execution(receipt)
            deployment = self.store.get_deployment(effect["deployment_id"])
            # 已由提供方确认的终态（如 DEPLOY FAILED）是确定性证据，不得被后续传输错误改写。
            if deployment.status not in {DeploymentStatus.SUCCEEDED, DeploymentStatus.FAILED, DeploymentStatus.ROLLED_BACK}:
                deployment.status, deployment.reconcile_state = DeploymentStatus.UNKNOWN, "UNKNOWN"
                self.store.put_deployment(deployment)
            self.repo.audit(effect["run_id"], "SIDE_EFFECT_UNKNOWN", {"effect_id": effect["id"], "reason": reason})
            run = self.store.get_run(effect["run_id"])
            phase = RunPhase.DEPLOYMENT_RECOVERY if run.phase in {RunPhase.DEPLOYMENT, RunPhase.G3} else run.phase
            self.transitions.transition(run.run_id, target_phase=phase, target_status=RunStatus.NEEDS_RECONCILIATION, expected_version=run.state_version)

    def reconcile(self, effect_id, *, principal_id):
        effect = self.store.runtime_get("effect", effect_id)
        self.rbac.require_human(principal_id)
        self.rbac.require_role(principal_id, "operator", self.store.get_run(effect["run_id"]).project_id)
        if effect["state"] in {"SUCCEEDED", "FAILED", "CANCELLED"}: return self.store.get_deployment(effect["deployment_id"])
        observation = self.providers[effect["target_id"]].query(effect["operation_id"])
        if not effect.get("dispatched", True) and observation.status == "NOT_FOUND":
            # 凭据已落库但请求从未发送、且提供方确认操作不存在：可确定收敛为取消，
            # 不能停留在 UNKNOWN 卡死对账与目标租约。
            return self._settle_cancelled(effect, principal_id, reason="CANCELLED_NEVER_DISPATCHED")
        if observation.status in {"UNKNOWN", "NOT_FOUND"}: raise EffectUncertain("外部操作仍未知，不能视为未发送或重发")
        return self._settle(effect, observation)

    def _settle_cancelled(self, effect, principal_id, *, reason):
        """把从未发送的副作用结算为 CANCELLED，并在无其他未决操作时释放目标租约。"""
        with self.store.transaction():
            stored = self.store.runtime_get("effect", effect["id"])
            if stored and stored["state"] in {"SUCCEEDED", "FAILED", "CANCELLED"}:
                return self.store.get_deployment(effect["deployment_id"])
            effect = dict(stored or effect)
            effect["state"] = "CANCELLED"
            self.store.runtime_put("effect", effect["id"], effect)
            receipt = self.store.find_tool_execution_by_key(effect["idempotency_key"])
            if receipt is not None and receipt.status not in {ToolExecutionStatus.SUCCEEDED, ToolExecutionStatus.FAILED, ToolExecutionStatus.CANCELLED}:
                receipt.status = ToolExecutionStatus.CANCELLED; receipt.settled_at = self.clock(); self.store.put_tool_execution(receipt)
            deployment = self.store.get_deployment(effect["deployment_id"])
            deployment.reconcile_state = reason
            if effect["action"] == "DEPLOY":
                deployment.status = DeploymentStatus.FAILED
                release = self.store.get_release(deployment.release_id)
                release.status = ReleaseStatus.READY; self.store.put_release(release)
            self.store.put_deployment(deployment)
            others_pending = any(e["state"] not in {"SUCCEEDED", "FAILED", "CANCELLED"}
                                 for e in self.store.runtime_list("effect")
                                 if e["deployment_id"] == effect["deployment_id"] and e["id"] != effect["id"])
            if not others_pending:
                self.release_lease(deployment)
            self.repo.audit(effect["run_id"], "SIDE_EFFECT_SETTLED_CANCELLED",
                            {"effect_id": effect["id"], "reason": reason, "reconciled_by": principal_id})
            return deployment

    def rollback(self, deployment_id, *, actor_id, authorization_id=None):
        deployment = self.store.get_deployment(deployment_id)
        original = next(e for e in self.store.runtime_list("effect") if e["deployment_id"] == deployment_id and e["action"] == "DEPLOY")
        key = digest({"rollback": deployment_id})
        existing_early = self.store.runtime_get("effect", key)
        if existing_early and existing_early["state"] == "SUCCEEDED":
            return deployment
        previous = original.get("previous_digest")
        # 鉴权与回滚基线检查先于任何执行凭据落库：本地可判定的拒绝（许可过期、
        # 角色失效、缺少基线）不得被记成"外部副作用未知"，否则会不可恢复地卡死对账。
        auth, release, target = self._validate(deployment.run_id, actor_id, authorization_id or deployment.authorization_id,
            deployment.target_ids[0], rollback=True, allow_consumed=authorization_id is None)
        if not previous: raise ValueError("缺少回滚基线")
        with self.store.transaction():
            existing = self.store.runtime_get("effect", key)
            if existing:
                if existing["state"] == "SUCCEEDED": return deployment
                if not (authorization_id and not existing.get("dispatched",True)):
                    raise EffectUncertain("回滚已有未决操作；需查询对账")
                self.repo.audit(deployment.run_id,"UNSENT_ROLLBACK_REAUTHORIZED",{"effect_id":key,"new_authorization_id":authorization_id})
            effect = {**original, "id": key, "idempotency_key": key, "operation_id": "rollback-" + uuid4().hex,
                      "action": "ROLLBACK", "state": "PREPARED", "actor_id": actor_id,"dispatched":False,
                      "authorization_id":authorization_id or deployment.authorization_id}
            self.store.runtime_put("effect", key, effect)
            self.store.put_tool_execution(ToolExecution(invocation_id=key, run_id=deployment.run_id, task_id=deployment_id,
                tool_name="rollback", params_hash=digest({"deployment": deployment_id, "previous": previous}),
                idempotency_key=key, external_operation_id=effect["operation_id"]))
        with self.store.transaction():
            if authorization_id:
                auth.consume();self.store.put_authorization(auth)
            effect.update(dispatched=True,state="DISPATCHING");self.store.runtime_put("effect",key,effect)
        try:
            observation = self.providers[target.target_id].execute(effect["operation_id"], "ROLLBACK", bundle=None,
                artifact_digest=release.artifact_digest, previous_digest=previous)
        except Exception:
            self._unknown(effect, "rollback_transport_unknown")
            raise EffectUncertain("回滚结果未知；已保留操作 ID，禁止重发") from None
        return self._settle(effect, observation)

    def release_lease(self, deployment):
        run = self.store.get_run(deployment.run_id)
        key = f"{run.project_id}/{deployment.target_ids[0]}"
        lease = self.store.runtime_get("target_lease", key)
        if lease and lease["deployment_id"] == deployment.deployment_id:
            self.store.runtime_put("target_lease", key, {**lease, "active": False})
