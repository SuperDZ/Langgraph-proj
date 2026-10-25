"""Phase 0 发布申请与人工许可。仅管理授权，不执行真实部署。"""

from datetime import timedelta
from uuid import uuid4

from ..contracts.enums import (
    ActorType, ApprovalDecision, AuthorizationRequestStatus, EventType,
    ReleaseStatus, ReleaseAction, RunPhase, RunStatus,
)
from ..contracts.models import Release, ReleaseAuthorizationRequest, ReleaseAuthorization, utc_now
from ..orchestration.store import atomic
from .rbac import AccessDenied


class ReleaseService:
    def __init__(self, store, transitions, rbac):
        self.store, self.transitions, self.rbac = store, transitions, rbac

    @atomic
    def create(self, *, run_id, commit_sha, artifact_digest):
        run = self.store.get_run(run_id)
        if run.phase is not RunPhase.RELEASE_AUTHORIZATION:
            raise ValueError("Release 仅能在 G2 放行后创建")
        gate = self.transitions.require_fresh_passing_gate(run_id, "G2")
        self.transitions.require_fresh_passing_gate(run_id, "G1")
        if run.baseline_versions.get("commit") and (commit_sha != run.baseline_versions["commit"]
                                                   or commit_sha != gate.commit_sha):
            raise ValueError("Release Commit 必须匹配当前 G2 验证版本")
        for existing in self.store.releases_for(run_id):
            if (existing.g2_gate_result_id, existing.commit_sha, existing.artifact_digest) == (
                gate.gate_result_id, commit_sha, artifact_digest
            ):
                return existing
        release = Release(
            release_id="release-" + uuid4().hex, run_id=run_id, project_id=run.project_id,
            spec_digest=run.baseline_versions["spec"], architecture_digest=run.baseline_versions["architecture"],
            commit_sha=commit_sha, artifact_digest=artifact_digest, g2_gate_result_id=gate.gate_result_id,
            version=str(len(self.store.releases_for(run_id)) + 1), status=ReleaseStatus.READY,
        )
        self.store.put_release(release)
        self.store.append_event(run_id=run_id, event_type=EventType.RELEASE_CREATED,
            actor_id="orchestrator", actor_type=ActorType.SYSTEM, payload_ref=release.model_dump_json(),
            idempotency_key=f"{release.release_id}:CREATED")
        return release

    @atomic
    def request(self, *, release_id, principal_id, environment_id, target_ids, action_scope, now=None):
        moment = now or utc_now()
        release = self.store.get_release(release_id)
        self.rbac.require_human(principal_id)
        self.rbac.assert_project_access(principal_id, release.project_id, moment)
        roles = self.rbac.roles_of(principal_id, release.project_id, moment)
        if not roles & {"project_owner", "operator", "release_approver"}:
            raise PermissionError("缺少发布申请角色")
        rollback_only=set(action_scope)=={ReleaseAction.ROLLBACK}
        if release.status is not ReleaseStatus.READY and not (rollback_only and release.status is ReleaseStatus.DEPLOYING):
            raise ValueError("Release 尚未就绪")
        self.transitions.require_fresh_passing_gate(release.run_id, "G1", now=moment)
        gate = self.transitions.require_fresh_passing_gate(release.run_id, "G2", now=moment)
        if gate.gate_result_id != release.g2_gate_result_id:
            raise ValueError("Release 基线已失效")
        run=self.store.get_run(release.run_id)
        if run.status in {RunStatus.COMPLETED,RunStatus.CANCELLED,RunStatus.FAILED}:raise ValueError("终态 Run 不接受新的发布申请")
        if run.phase is RunPhase.RELEASE_AUTHORIZATION and run.status is RunStatus.BLOCKED:
            self.transitions.transition(run.run_id,target_status=RunStatus.WAITING_APPROVAL,expected_version=run.state_version)
        request = ReleaseAuthorizationRequest(
            authorization_request_id="auth-request-" + uuid4().hex,
            release_id=release_id, run_id=release.run_id, environment_id=environment_id,
            target_ids=target_ids, action_scope=action_scope, requested_by=principal_id,
            policy_version="release-policy-v1.2", requested_at=moment,
            expires_at=moment + timedelta(minutes=60),
        )
        self.store.put_authorization_request(request)
        registered = {}
        for target_id in target_ids:
            target = self.store.runtime_get("deployment_target", f"{release.project_id}/{target_id}")
            if target:
                registered[target_id] = target["digest"]
        if registered:
            self.store.runtime_put("authorization_targets", request.authorization_request_id, registered)
        self.store.append_event(run_id=release.run_id, event_type=EventType.RELEASE_AUTHORIZATION_REQUESTED,
            actor_id=principal_id, actor_type=ActorType.HUMAN, payload_ref=request.model_dump_json(),
            idempotency_key=f"{request.authorization_request_id}:REQUESTED")
        return request

    def decide(self, *, request_id, principal_id, decision, now=None):
        """拒绝授权的审计在失败事务外单独追加，业务状态保持不变。"""
        try:
            return self._decide(request_id=request_id, principal_id=principal_id, decision=decision, now=now)
        except AccessDenied as exc:
            request = self.store.get_authorization_request(request_id)
            self.store.append_event(run_id=request.run_id, event_type=EventType.ACCESS_DENIED,
                actor_id=principal_id, actor_type=ActorType.SYSTEM, payload_ref=str(exc),
                idempotency_key=f"{request_id}:DENIED:{principal_id}")
            raise

    @atomic
    def _decide(self, *, request_id, principal_id, decision, now=None):
        moment = now or utc_now()
        request = self.store.get_authorization_request(request_id)
        release = self.store.get_release(request.release_id)
        self.rbac.require_human(principal_id)
        self.rbac.assert_project_access(principal_id, release.project_id, moment)
        if "release_approver" not in self.rbac.roles_of(principal_id, release.project_id, moment):
            from .rbac import AccessDenied
            raise AccessDenied(principal_id, "缺少 release_approver 角色")
        if request.status is not AuthorizationRequestStatus.PENDING:
            raise ValueError("发布申请已经决策")
        if request.expires_at <= moment:
            raise ValueError("发布申请已过期")
        self.transitions.require_fresh_passing_gate(release.run_id, "G1", now=moment)
        gate = self.transitions.require_fresh_passing_gate(release.run_id, "G2")
        rollback_only=set(request.action_scope)=={ReleaseAction.ROLLBACK}
        if gate.gate_result_id != release.g2_gate_result_id or (release.status is not ReleaseStatus.READY and not (rollback_only and release.status is ReleaseStatus.DEPLOYING)):
            raise ValueError("Release 基线已失效")
        run=self.store.get_run(release.run_id)
        if decision is ApprovalDecision.APPROVE and run.status in {RunStatus.COMPLETED,RunStatus.CANCELLED,RunStatus.FAILED,RunStatus.CANCEL_REQUESTED,RunStatus.CANCELLING}:
            raise ValueError("Run 已停止，拒绝签发新的许可")
        if decision is ApprovalDecision.APPROVE and run.status is RunStatus.NEEDS_RECONCILIATION and not rollback_only:
            raise ValueError("待对账状态仅允许申请恢复回滚许可")
        request.status = (AuthorizationRequestStatus.APPROVED if decision is ApprovalDecision.APPROVE
                          else AuthorizationRequestStatus.REJECTED)
        request.decided_by = principal_id
        self.store.put_authorization_request(request)
        authorization = None
        if decision is ApprovalDecision.APPROVE:
            authorization = ReleaseAuthorization(
                authorization_id="auth-" + uuid4().hex, authorization_request_id=request_id,
                release_id=release.release_id, project_id=release.project_id,
                environment_id=request.environment_id, target_ids=request.target_ids,
                artifact_digest=release.artifact_digest, commit_sha=release.commit_sha,
                action_scope=request.action_scope, issued_by=principal_id, issued_at=moment,
                expires_at=min(request.expires_at, moment + timedelta(minutes=60)), max_uses=1,
            )
            self.store.put_authorization(authorization)
            targets = self.store.runtime_get("authorization_targets", request_id)
            if targets:
                self.store.runtime_put("authorization_targets", authorization.authorization_id, targets)
        else:
            run = self.store.get_run(release.run_id)
            if run.status not in {RunStatus.BLOCKED,RunStatus.CANCEL_REQUESTED,RunStatus.CANCELLING,RunStatus.CANCELLED,RunStatus.FAILED,RunStatus.COMPLETED,RunStatus.NEEDS_RECONCILIATION}:
                self.transitions.transition(run.run_id, target_status=RunStatus.BLOCKED,
                                            expected_version=run.state_version)
        self.store.append_event(run_id=release.run_id, event_type=EventType.RELEASE_AUTHORIZATION_DECIDED,
            actor_id=principal_id, actor_type=ActorType.HUMAN, payload_ref=request.model_dump_json(),
            idempotency_key=f"{request_id}:DECIDED")
        return authorization

    @atomic
    def revoke(self, authorization_id, principal_id):
        authorization = self.store.get_authorization(authorization_id)
        self.rbac.require_human(principal_id)
        self.rbac.require_role(principal_id, "release_approver", authorization.project_id)
        from ..contracts.enums import AuthorizationStatus
        authorization.status = AuthorizationStatus.REVOKED
        self.store.put_authorization(authorization)
        release = self.store.get_release(authorization.release_id)
        self.store.append_event(run_id=release.run_id, event_type=EventType.RELEASE_AUTHORIZATION_REVOKED,
            actor_id=principal_id, actor_type=ActorType.HUMAN, payload_ref=authorization_id,
            idempotency_key=f"{authorization_id}:REVOKED")
