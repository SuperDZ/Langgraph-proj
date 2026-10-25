"""G1 人工确认请求的幂等服务。

规范约束（§2.3 / §8.4 / REQ-047）：
- **仅GateEvaluator** 在首次评估 G1 时通过内部 ``ensure_required()``
  幂等创建 ApprovalRequest
- 无公开 ``POST /approval-requests`` 创建口
- Agent、用户均不能直接伪造 G1 申请
- 用户只能在optional 策略下要求开启额外确认，或对现有请求作决定
- 人工确认只能批准指定内容版本：Spec/架构的任何语义变更使旧批准失效
- 过期、撤销或审批身份不匹配均拒绝
"""

from __future__ import annotations

from datetime import datetime, timedelta
from uuid import uuid4

from ..contracts.enums import (
    ActorType,
    ApprovalDecision,
    ApprovalSubjectType,
    EventType,
    PrincipalType,
    RunStatus,
)
from ..contracts.models import ApprovalRequest, Run, digest_of, utc_now
from ..orchestration.store import InMemoryStore, atomic
from .rbac import RBACService

GATE_EVALUATOR = "GATE_EVALUATOR"


class ApprovalError(Exception):
    """审批创建或决策被拒绝。"""


class ApprovalRequestService:
    """G1 审批请求的唯一创建者与决策入口。"""

    def __init__(self, store: InMemoryStore, rbac: RBACService | None = None) -> None:
        self.store = store
        self.rbac = rbac

    # ------------------------------------------------------------------
    # 创建（仅 GateEvaluator）
    # ------------------------------------------------------------------

    @atomic
    def ensure_required(
        self,
        *,
        run_id: str,
        subject_type: ApprovalSubjectType,
        input_digest: str,
        required_roles: list[str],
        request_version: int,
        expires_in_hours: int,
        actor_id: str,
        now: datetime | None = None,
    ) -> tuple[ApprovalRequest, bool]:
        """幂等创建。

        返回 ``(request, created)``。命中同输入下仍可复用的请求时返回
        ``(request, False)``；已撤销、已过期或已被拒绝的旧请求不复用，
        而是以递增的 ``request_version`` 重新创建（规范 §7.5 唯一索引
        ApprovalRequest(run_id, subject_type, input_digest, request_version)）。
        """
        if actor_id != GATE_EVALUATOR:
            raise ApprovalError(
                f"只有 {GATE_EVALUATOR} 可创建 G1 审批请求，收到 {actor_id}"
            )

        moment = now or utc_now()
        same_subject = [
            existing for existing in self.store.approval_requests_for(run_id)
            if existing.subject_type is subject_type and existing.input_digest == input_digest
        ]
        # 同一输入版本已被真人明确拒绝：拒绝是对内容的终局裁定，不自动重建
        # 请求；需变更内容（新 digest）后重新走流程。
        rejected = [existing for existing in same_subject if existing.decision is ApprovalDecision.REJECT]
        if rejected:
            return max(rejected, key=lambda r: r.request_version), False
        # 已撤销/已过期的请求不能被幂等复用，否则同一输入将永远无法再次审批；
        # 命中可复用请求时直接返回，否则以递增版本重新创建。
        reusable = [existing for existing in same_subject if self._reusable(existing, moment)]
        if reusable:
            return max(reusable, key=lambda r: r.request_version), False
        highest = max((existing.request_version for existing in same_subject), default=0)
        request_version = max(request_version, highest + 1)

        request = ApprovalRequest(
            approval_id=f"apr-{uuid4().hex}",
            run_id=run_id,
            subject_type=subject_type,
            input_digest=input_digest,
            request_version=request_version,
            required_roles=list(required_roles),
            expires_at=moment + timedelta(hours=expires_in_hours),
            created_by=GATE_EVALUATOR,
            created_at=moment,
        )
        self.store.put_approval_request(request)

        self.store.append_event(
            run_id=run_id,
            event_type=EventType.APPROVAL_REQUEST_CREATED,
            actor_id=GATE_EVALUATOR,
            actor_type=ActorType.SYSTEM,
            payload_ref=(
                f"subject={subject_type.value};digest={input_digest};"
                f"version={request_version};expires_at={request.expires_at.isoformat()}"
            ),
            idempotency_key=(
                f"{run_id}:APPROVAL_CREATED:{subject_type.value}:"
                f"{input_digest}:{request_version}"
            ),
        )
        return request, True

    @staticmethod
    def _reusable(request: ApprovalRequest, moment: datetime) -> bool:
        """请求是否仍可被复用（尚未撤销/过期，且未被拒绝）。"""
        if request.revoked or request.expires_at <= moment:
            return False
        return True

    def get(self, approval_id: str) -> ApprovalRequest:
        return self.store.get_approval_request(approval_id)

    def list_for_run(self, run_id: str) -> list[ApprovalRequest]:
        return self.store.approval_requests_for(run_id)

    # ------------------------------------------------------------------
    # 决策（仅合格真人）
    # ------------------------------------------------------------------

    @atomic
    def decide(
        self,
        *,
        approval_id: str,
        decision: ApprovalDecision,
        principal_id: str,
        now: datetime | None = None,
        reason: str | None = None,
    ) -> ApprovalRequest:
        """人类以 APPROVE|REJECT 作决定；拒绝自批准和 Agent 身份。"""
        moment = now or utc_now()
        request = self.get(approval_id)

        if self.rbac is None:
            raise ApprovalError("未配置可信 RBAC 服务")
        self.rbac.require_human(principal_id)
        run = self.store.get_run(request.run_id)
        self.rbac.assert_project_access(principal_id, run.project_id, moment)
        held_roles = self.rbac.roles_of(principal_id, run.project_id, moment)
        if not held_roles.intersection(request.required_roles):
            raise ApprovalError(
                f"主体 {principal_id} 不具备任一必需角色 {request.required_roles}"
            )
        current_input_digest = compute_input_digest(
            run.baseline_versions.get("spec", ""), run.baseline_versions.get("architecture", "")
        )
        if request.input_digest != current_input_digest:
            raise ApprovalError(
                "输入版本已变更，旧批准失效；需基于新版本重新请求审批"
            )

        try:
            request.apply_decision(decision, principal_id, moment, reason)
        except ValueError as exc:
            raise ApprovalError(str(exc)) from exc

        self.store.put_approval_request(request)
        self.store.append_event(
            run_id=request.run_id,
            event_type=EventType.APPROVAL_REQUEST_DECIDED,
            actor_id=principal_id,
            actor_type=ActorType.HUMAN,
            payload_ref=(
                f"approval={approval_id};decision={decision.value};"
                f"digest={request.input_digest}"
            ),
            idempotency_key=f"{request.run_id}:APPROVAL_DECIDED:{approval_id}",
        )
        return request

    @atomic
    def revoke(self, *, approval_id: str, principal_id: str, reason: str,
               now: datetime | None = None) -> ApprovalRequest:
        """有权真人撤销尚未决策的请求。"""
        request = self.get(approval_id)
        if self.rbac is None:
            raise ApprovalError("未配置可信 RBAC 服务")
        moment = now or utc_now()
        self.rbac.require_human(principal_id)
        run = self.store.get_run(request.run_id)
        self.rbac.assert_project_access(principal_id, run.project_id, moment)
        if not self.rbac.roles_of(principal_id, run.project_id, moment).intersection(request.required_roles):
            raise ApprovalError("缺少撤销审批的角色")
        if request.revoked:
            return request
        request.revoke(principal_id)
        self.store.put_approval_request(request)
        from ..orchestration.state_transition import StateTransitionService
        from ..contracts.enums import GateStatus
        transitions = StateTransitionService(self.store)
        for gate in self.store.gate_results_for(request.run_id):
            if gate.status in {GateStatus.PASSED, GateStatus.PENDING}:
                transitions.transition_gate(gate, GateStatus.STALE, moment=moment)
        self.store.append_event(
            run_id=request.run_id,
            event_type=EventType.APPROVAL_REQUEST_REVOKED,
            actor_id=principal_id,
            actor_type=ActorType.HUMAN,
            payload_ref=f"approval={approval_id};reason={reason}",
            idempotency_key=f"{request.run_id}:APPROVAL_REVOKED:{approval_id}",
        )
        return request

    def has_effective_approval(
        self, run_id: str, subject_type: ApprovalSubjectType, input_digest: str
    ) -> bool:
        """检查是否存在绑定当前输入摘要的有效批准。"""
        moment = utc_now()
        return any(
            r.subject_type is subject_type
            and r.input_digest == input_digest
            and self.is_effective(r, now=moment)
            for r in self.list_for_run(run_id)
        )

    def is_effective(self, request: ApprovalRequest, *, now=None) -> bool:
        """使用批准时与使用时的有效期、身份和项目角色共同判断。"""
        from .rbac import AccessDenied
        moment = now or utc_now()
        if self.rbac is None or not request.is_effective(moment) or not request.decided_by:
            return False
        try:
            run = self.store.get_run(request.run_id)
            self.rbac.require_human(request.decided_by)
            roles = self.rbac.roles_of(request.decided_by, run.project_id, moment)
            return bool(roles.intersection(request.required_roles))
        except (AccessDenied, KeyError):
            return False


def compute_input_digest(spec_digest: str, architecture_digest: str) -> str:
    """G1 的输入摘要绑定 Spec 与架构的同版本有效性（REQ-005/ REQ-008）。"""
    return digest_of(f"spec={spec_digest};arch={architecture_digest}")
