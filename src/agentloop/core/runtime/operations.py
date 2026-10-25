"""G3 恢复、可恢复取消与持久周期巡检；维护子 Run 不写父交付状态。"""

from uuid import uuid4
from datetime import timedelta, datetime
from ..approvals import ApprovalRequestService
from ..contracts.enums import (ActorType, GateId, GateStatus, IssueCategory, IssueStatus,
    ReleaseAction, ReleaseStatus, RunPhase, RunStatus, RunType, Severity, TrustLevel)
from ..contracts.models import GateEvaluationRequest, Issue, utc_now
from ..orchestration import GateEvaluator
from ..routing import LoopRouter
from .configuration import digest
from .effects import EffectUncertain


class DeploymentCoordinator:
    def __init__(self, executor):
        self.executor, self.repo, self.store = executor, executor.repo, executor.store
        self.transitions, self.rbac = executor.transitions, executor.rbac
        self.gates = GateEvaluator(self.store, self.transitions, ApprovalRequestService(self.store, self.rbac), archive=self.repo.archive)
        self.router = LoopRouter(self.store)

    def finalize(self, deployment_id, *, actor_id):
        deployment = self.store.get_deployment(deployment_id)
        run = self.store.get_run(deployment.run_id)
        self.executor._identity(run.run_id, actor_id)
        if run.status is RunStatus.COMPLETED: return run
        if run.status in {RunStatus.CANCEL_REQUESTED, RunStatus.CANCELLING, RunStatus.NEEDS_RECONCILIATION}:
            raise EffectUncertain("取消或对账期间不能放行交付")
        effects = [e for e in self.store.runtime_list("effect") if e["deployment_id"] == deployment_id and e["action"] == "DEPLOY"]
        effect = effects[0]
        if effect["state"] != "SUCCEEDED": return self.recover(deployment_id, actor_id=actor_id)
        provider = self.executor.providers[deployment.target_ids[0]]
        try:health = provider.health(deployment.release_artifact_digest)
        except Exception:health={"artifact_digest":None,"healthy":False,"evidence":"deployment target unreachable"}
        authorization = self.store.get_authorization(deployment.authorization_id)
        artifact = self.repo.archive.put(run_id=run.run_id, kind="DEPLOYMENT_EVIDENCE", producer="deployment-observer",
            trust=TrustLevel.VERIFIED_INTERNAL, value={"deployment_id": deployment_id, "effect_id": effect["id"],
                "artifact_digest": deployment.release_artifact_digest, "health": health, "observed_at": self.executor.clock().isoformat()})
        if run.phase is RunPhase.DEPLOYMENT:
            run = self.transitions.transition(run.run_id, target_phase=RunPhase.G3, expected_version=run.state_version)
        result = self.gates.evaluate(GateEvaluationRequest(run_id=run.run_id, gate_id=GateId.G3,
            policy_version=self.gates.policy_version, input_digest=artifact.sha256, evidence_artifact_id=artifact.artifact_id,
            deployment_id=deployment_id, authorization_id=deployment.authorization_id, target_environment=deployment.environment_id,
            artifact_digest=deployment.release_artifact_digest, smoke_check_passed=health.get("healthy") is True,
            health_check_passed=health.get("healthy") is True, rollback_ready=bool(effect["previous_digest"]) and ReleaseAction.ROLLBACK in authorization.action_scope))
        deployment = self.store.get_deployment(deployment_id)
        deployment.gate3_result_id = result.gate_result_id; self.store.put_deployment(deployment)
        if result.status is GateStatus.PASSED:
            release=self.store.get_release(deployment.release_id);release.status=ReleaseStatus.DEPLOYED;self.store.put_release(release)
            self.executor.release_lease(deployment)
            for issue in self.store.list_issues(run.run_id):
                if issue.category is IssueCategory.DEPLOY_FAILURE and issue.severity is Severity.MEDIUM:
                    issue.status = IssueStatus.RESOLVED; issue.evidence_artifact_ids.append(artifact.artifact_id); self.store.put_issue(issue)
            return self.transitions.advance_to_delivery(run.run_id, expected_version=self.store.get_run(run.run_id).state_version)
        return self.recover(deployment_id, actor_id=actor_id)

    def recover(self, deployment_id, *, actor_id):
        deployment = self.store.get_deployment(deployment_id)
        run = self.store.get_run(deployment.run_id)
        if run.phase in {RunPhase.DEPLOYMENT, RunPhase.G3}:
            run = self.transitions.transition(run.run_id, target_phase=RunPhase.DEPLOYMENT_RECOVERY, expected_version=run.state_version)
        try:
            deployment = self.executor.rollback(deployment_id, actor_id=actor_id)
        except EffectUncertain:
            return self.store.get_run(run.run_id)
        rollback = next(e for e in self.store.runtime_list("effect") if e["deployment_id"] == deployment_id and e["action"] == "ROLLBACK")
        try:health = self.executor.providers[deployment.target_ids[0]].health(rollback["previous_digest"])
        except Exception:health={"artifact_digest":None,"healthy":False,"evidence":"rollback target unreachable"}
        if health.get("healthy") is not True:
            self.executor._unknown(rollback, "rollback_health_unconfirmed",force=True)
            return self.store.get_run(run.run_id)
        with self.store.transaction():
            evidence = self.repo.archive.put(run_id=run.run_id, kind="RECOVERY_EVIDENCE", producer="operations-expert",
                value={"deployment_id": deployment_id, "rollback_effect": rollback["id"], "health": health}, trust=TrustLevel.VERIFIED_INTERNAL)
            self.store.runtime_put("recovery", deployment_id, {"safe": True, "artifact_id": evidence.artifact_id, "previous_digest": rollback["previous_digest"]})
            deployment.reconcile_state = "SAFE_ROLLED_BACK"; self.store.put_deployment(deployment)
            release=self.store.get_release(deployment.release_id);release.status=ReleaseStatus.READY;self.store.put_release(release)
            issue_id = "deployment-failure-" + deployment_id
            if not any(i.issue_id == issue_id for i in self.store.list_issues(run.run_id)):
                self.router.route(Issue(issue_id=issue_id, run_id=run.run_id, category=IssueCategory.DEPLOY_FAILURE,
                    severity=Severity.MEDIUM, description="部署/G3 失败，环境已安全回滚；需要证据分类整改",
                    evidence_artifact_ids=[evidence.artifact_id]), source_event_id=evidence.artifact_id)
            self.executor.release_lease(deployment)
            current = self.store.get_run(run.run_id)
            if self.store.runtime_get("cancellation", run.run_id):
                return current
            return self.transitions.transition(run.run_id, target_status=RunStatus.BLOCKED, expected_version=current.state_version)

    def remediate(self, deployment_id, *, cause, principal_id):
        cause = IssueCategory(cause)
        phases = {IssueCategory.ENV_DEFECT: RunPhase.RELEASE_AUTHORIZATION, IssueCategory.CODE_DEFECT: RunPhase.ENGINEERING,
                  IssueCategory.SPEC_DEFECT: RunPhase.PRODUCT, IssueCategory.ARCH_DEFECT: RunPhase.ARCHITECTURE}
        if cause not in phases: raise ValueError("部署整改根因不受支持")
        deployment = self.store.get_deployment(deployment_id)
        run = self.store.get_run(deployment.run_id)
        self.rbac.require_human(principal_id); self.rbac.require_role(principal_id, "project_owner", run.project_id)
        safe = self.store.runtime_get("recovery", deployment_id)
        if not safe or not safe["safe"] or run.phase is not RunPhase.DEPLOYMENT_RECOVERY or run.status is not RunStatus.BLOCKED:
            raise ValueError("只有已验证安全的恢复状态才能返工")
        if self.executor.providers[deployment.target_ids[0]].health(safe["previous_digest"]).get("healthy") is not True:
            raise ValueError("环境已变化，必须重新对账")
        with self.store.transaction():
            issue = next(i for i in self.store.list_issues(run.run_id) if i.issue_id == "deployment-failure-" + deployment_id)
            issue.root_cause = cause
            classification = self.repo.audit(run.run_id, "RECOVERY_CLASSIFIED_BY_HUMAN", {"principal_id": principal_id, "cause": cause.value,
                "evidence": safe["artifact_id"], "deployment_id": deployment_id})
            routing = self.router.route(issue, source_event_id=classification.artifact_id)
            self.repo.archive.put(run_id=run.run_id,kind="RECOVERY_WORK_ORDER",producer="loop-router",
                value={"deployment_id":deployment_id,"routing":routing.model_dump(mode="json"),"evidence":safe["artifact_id"]},trust=TrustLevel.VERIFIED_INTERNAL)
            target_status = RunStatus.WAITING_APPROVAL if cause is IssueCategory.ENV_DEFECT else RunStatus.RUNNING
            return self.transitions.transition(run.run_id, target_phase=phases[cause], target_status=target_status,
                expected_version=run.state_version, reason="经证据分类的部署整改")

    def terminate(self, deployment_id, *, principal_id):
        deployment = self.store.get_deployment(deployment_id)
        run = self.store.get_run(deployment.run_id)
        self.rbac.require_human(principal_id); self.rbac.require_role(principal_id, "project_owner", run.project_id)
        safe = self.store.runtime_get("recovery", deployment_id)
        if not safe or not safe["safe"] or run.phase is not RunPhase.DEPLOYMENT_RECOVERY or run.status is not RunStatus.BLOCKED:
            raise ValueError("终止需要已核实的安全恢复证据")
        if self.executor.providers[deployment.target_ids[0]].health(safe["previous_digest"]).get("healthy") is not True:
            raise ValueError("环境不再安全")
        self.repo.audit(run.run_id, "TERMINATION_AUTHORIZED", {"principal_id": principal_id, "evidence": safe["artifact_id"]})
        return self.transitions.transition(run.run_id, target_status=RunStatus.FAILED, expected_version=run.state_version)


class CancellationService:
    def __init__(self, coordinator):
        self.coordinator = coordinator
        self.executor, self.store, self.transitions, self.rbac = coordinator.executor, coordinator.store, coordinator.transitions, coordinator.rbac

    def request(self, run_id, *, principal_id):
        self.rbac.require_human(principal_id)
        self.rbac.require_role(principal_id, "project_owner", self.store.get_run(run_id).project_id)
        with self.store.transaction():
            run = self.store.get_run(run_id)
            if run.status is RunStatus.CANCELLED: return run
            if run.status not in {RunStatus.CANCEL_REQUESTED, RunStatus.CANCELLING, RunStatus.NEEDS_RECONCILIATION}:
                self.executor.repo.audit(run_id, "CANCELLATION_REQUESTED", {"principal_id": principal_id})
                run = self.transitions.transition(run_id, target_status=RunStatus.CANCEL_REQUESTED, expected_version=run.state_version)
            self.store.runtime_put("cancellation", run_id, {"requested_by": principal_id, "requested": True})
            return run

    def settle(self, run_id, *, principal_id, actor_id):
        self.rbac.require_human(principal_id)
        self.rbac.require_role(principal_id, "operator", self.store.get_run(run_id).project_id)
        if not self.store.runtime_get("cancellation", run_id): raise ValueError("没有取消意图")
        effects = [e for e in self.store.runtime_list("effect") if e["run_id"] == run_id]
        policy=self.executor._identity(run_id,actor_id) if effects else None
        for effect in effects:
            target,_=self.executor.target(self.store.get_run(run_id).project_id,effect["target_id"])
            if target.target_id not in policy.target_ids or f"cap.deploy.{target.environment}" not in policy.grants():
                raise PermissionError("取消/补偿执行主体超出目标能力范围")
            if effect["state"] not in {"SUCCEEDED", "FAILED", "CANCELLED"}:
                provider=self.executor.providers[effect["target_id"]]
                signal_id="cancel-signal-"+effect["id"]
                if hasattr(provider,"cancel") and not self.store.runtime_get("cancellation_signal",signal_id):
                    # 取消信号的意图先落库。未知响应时不重复发送，继续查询原操作。
                    self.store.runtime_put("cancellation_signal",signal_id,{"run_id":run_id,"operation_id":effect["operation_id"],"status":"STARTED"})
                    try:
                        observation=provider.cancel(effect["operation_id"])
                        self.store.runtime_put("cancellation_signal",signal_id,{"run_id":run_id,"operation_id":effect["operation_id"],"status":observation.status})
                    except Exception:
                        self.store.runtime_put("cancellation_signal",signal_id,{"run_id":run_id,"operation_id":effect["operation_id"],"status":"UNKNOWN"})
                    self.executor.repo.audit(run_id,"CANCELLATION_SIGNAL_RECORDED",self.store.runtime_get("cancellation_signal",signal_id))
                try: self.executor.reconcile(effect["id"], principal_id=principal_id)
                except EffectUncertain:
                    self.executor._unknown(effect, "cancellation_requires_reconciliation")
                    return self.store.get_run(run_id)
        for deployment in self.store.deployments_for(run_id):
            from ..contracts.enums import DeploymentStatus
            if deployment.environment_id == "simulation": continue
            original=next((e for e in self.store.runtime_list("effect") if e["deployment_id"]==deployment.deployment_id and e["action"]=="DEPLOY"),None)
            if original and original["state"]=="CANCELLED" and not original.get("dispatched",True):
                self.store.runtime_put("recovery",deployment.deployment_id,{"safe":True,"reason":"NO_REQUEST_DISPATCHED"})
                self.executor.release_lease(deployment)
                continue
            if deployment.status is not DeploymentStatus.ROLLED_BACK:
                try: self.coordinator.recover(deployment.deployment_id, actor_id=actor_id)
                except EffectUncertain: return self.store.get_run(run_id)
            safe = self.store.runtime_get("recovery", deployment.deployment_id)
            if not safe or not safe["safe"]: return self.store.get_run(run_id)
        run = self.store.get_run(run_id)
        if run.status is RunStatus.CANCELLED: return run
        if self.store.pending_tool_executions(run_id): return run
        if run.status in {RunStatus.CANCEL_REQUESTED, RunStatus.NEEDS_RECONCILIATION}:
            run = self.transitions.transition(run_id, target_status=RunStatus.CANCELLING, expected_version=run.state_version)
        return self.transitions.transition(run_id, target_status=RunStatus.CANCELLED, expected_version=run.state_version)


class MaintenanceService:
    def __init__(self, executor):
        self.executor, self.store = executor, executor.store
        self.transitions, self.repo = executor.transitions, executor.repo

    def schedule(self, run_id, target_id, *, principal_id, interval_seconds=300):
        run = self.store.get_run(run_id)
        self.executor.rbac.require_human(principal_id)
        self.executor.rbac.require_role(principal_id, "project_owner", run.project_id)
        if run.phase is not RunPhase.DELIVERY or run.status is not RunStatus.COMPLETED or interval_seconds < 1:
            raise ValueError("巡检需已完成的父交付和正数周期")
        self.executor.target(run.project_id, target_id)
        key = digest({"run": run_id, "target": target_id})
        with self.store.transaction():
            old = self.store.runtime_get("maintenance_schedule", key)
            if old: return old
            record = {"id": key, "parent": run_id, "target": target_id, "interval": interval_seconds,
                "next_due": self.executor.clock().isoformat(), "enabled": True}
            self.store.runtime_put("maintenance_schedule", key, record)
            return record

    def tick(self, parent_run_id=None):
        children = []
        for record in self.store.runtime_list("maintenance_schedule"):
            if parent_run_id is not None and record["parent"] != parent_run_id: continue
            now = self.executor.clock()
            if not record["enabled"] or record["next_due"] > now.isoformat(): continue
            with self.store.transaction():
                current = self.store.runtime_get("maintenance_schedule", record["id"])
                if current["next_due"] != record["next_due"]: continue
                parent = self.store.get_run(record["parent"])
                principal=self.executor.rbac.get_principal(self.executor.service_principal)
                from ..contracts.enums import PrincipalType
                if principal.principal_type is not PrincipalType.SYSTEM_SERVICE: raise PermissionError("巡检需独立服务身份")
                self.executor.rbac.require_role(self.executor.service_principal,"side_effect_executor",parent.project_id)
                key = digest({"schedule": record["id"], "due": record["next_due"]})
                child_id = "maintenance-" + key[:24]
                if not self.store.find_run(child_id):
                    self.transitions.create_run(run_id=child_id, run_type=RunType.MAINTENANCE, project_id=parent.project_id,
                        parent_run_id=parent.run_id, trigger_source="SCHEDULE", config_snapshot_id=parent.config_snapshot_id,
                        baseline_versions=parent.baseline_versions)
                    self.transitions.transition(child_id, target_phase=RunPhase.MAINTENANCE, target_status=RunStatus.RUNNING)
                current["next_due"] = (now + timedelta(seconds=record["interval"])).isoformat()
                self.store.runtime_put("maintenance_schedule", record["id"], current)
                self.store.runtime_put("maintenance_pending", child_id, {"run_id": child_id, "target": record["target"], "done": False})
        # 重启后也处理已经创建而未落观察结果的子 Run。
        for pending in self.store.runtime_list("maintenance_pending"):
            if pending["done"]: continue
            child = self.store.get_run(pending["run_id"])
            if parent_run_id is not None and child.parent_run_id != parent_run_id: continue
            if child.status is not RunStatus.RUNNING: continue
            deployments = self.store.deployments_for(child.parent_run_id)
            latest = deployments[-1]
            try:health = self.executor.providers[pending["target"]].health(latest.release_artifact_digest)
            except Exception:health={"artifact_digest":None,"healthy":False,"evidence":"inspection target unreachable"}
            with self.store.transaction():
                self.repo.audit(child.run_id, "MAINTENANCE_OBSERVATION", health)
                if health.get("healthy") is True:
                    self.transitions.transition(child.run_id, target_status=RunStatus.COMPLETED)
                else:
                    incident_id = "incident-" + child.run_id
                    self.transitions.create_run(run_id=incident_id, run_type=RunType.INCIDENT, project_id=child.project_id,
                        parent_run_id=child.run_id, trigger_source="MAINTENANCE_FAILURE", config_snapshot_id=child.config_snapshot_id)
                    self.transitions.transition(incident_id, target_phase=RunPhase.INCIDENT, target_status=RunStatus.RUNNING)
                    self.transitions.transition(incident_id, target_status=RunStatus.BLOCKED)
                    self.transitions.transition(child.run_id, target_status=RunStatus.BLOCKED)
                pending["done"] = True; self.store.runtime_put("maintenance_pending", child.run_id, pending)
                children.append(self.store.get_run(child.run_id))
        return children
