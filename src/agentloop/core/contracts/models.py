"""严格 Pydantic 契约。

设计要点（规范 §7.2、§12执行约束）：
- Agent 侧可提交的模型一律extra="forbid"，多余字段直接拒绝而不是静默丢弃
- 服务端专属字段（routed_leader、routed_department、final_gate_result）
  不出现在任何 Agent 可提交的 Schema 里，从类型层面消除注入路径
- 所有带版本的记录都带 ``policy_version`` 或 ``state_version``，保证历史可回放
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from typing import Any

from pydantic import BaseModel, ConfigDict, Field, StrictBool, field_validator, model_validator

from .enums import (
    ActorType,
    ApprovalDecision,
    ApprovalSubjectType,
    AuthorizationRequestStatus,
    AuthorizationStatus,
    ClarificationKind,
    ClarificationStatus,
    Department,
    DeploymentStatus,
    EventType,
    GateId,
    GateStatus,
    IssueCategory,
    IssueStatus,
    LeaderRole,
    PrincipalType,
    ReleaseAction,
    ReleaseStatus,
    RiskWaiverStatus,
    RunPhase,
    RunStatus,
    RunType,
    Severity,
    SubtaskStatus,
    ToolExecutionStatus,
    TrustLevel,
)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


def digest_of(payload: str) -> str:
    """内容摘要。用于 input_digest / artifact 引用，禁止用模型自报值代替。"""
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


class StrictModel(BaseModel):
    """所有契约的基类：拒绝未知字段。"""

    model_config = ConfigDict(extra="forbid", validate_assignment=True)


# --------------------------------------------------------------------------
# 主体与权限
# --------------------------------------------------------------------------


class Principal(StrictModel):
    principal_id: str
    principal_type: PrincipalType
    identity_provider_ref: str
    status: str = "ACTIVE"


class RoleBinding(StrictModel):
    """RBAC 只由服务端维护，Agent 不可写入。"""

    binding_id: str
    principal_id: str
    role_id: str
    scope_type: str
    scope_id: str
    valid_from: datetime
    valid_until: datetime | None = None

    def is_effective_at(self, moment: datetime) -> bool:
        if moment < self.valid_from:
            return False
        return self.valid_until is None or moment < self.valid_until


class CapabilitySet(StrictModel):
    """cap.* 集合。命名规范见 §2.8 与附录 A。"""

    grants: frozenset[str] = Field(default_factory=frozenset)

    def intersect(self, other: "CapabilitySet | frozenset[str] | set[str]") -> "CapabilitySet":
        other_grants = other.grants if isinstance(other, CapabilitySet) else frozenset(other)
        return CapabilitySet(grants=self.grants & other_grants)

    def denied_by(self, denied: frozenset[str] | set[str]) -> "CapabilitySet":
        """显式 deny 永远优先。"""
        return CapabilitySet(grants=self.grants - frozenset(denied))


# --------------------------------------------------------------------------
# Run 与子任务
# --------------------------------------------------------------------------


class Run(StrictModel):
    """执行单元。phase 与 status 正交；state_version供原子 CAS。"""

    run_id: str
    run_type: RunType
    parent_run_id: str | None = None
    root_run_id: str = ""
    project_id: str
    phase: RunPhase
    status: RunStatus
    state_version: int = 1
    baseline_versions: dict[str, str] = Field(default_factory=dict)
    trigger_source: str
    config_snapshot_id: str

    @model_validator(mode="after")
    def _root_run_only_for_delivery(self) -> "Run":
        if self.run_type is not RunType.DELIVERY and self.parent_run_id is None:
            raise ValueError(
                f"run_type={self.run_type.value} 必须有 parent_run_id；"
                "仅根 DELIVERY Run 可以没有父 Run"
            )
        return self

    def version_digest(self) -> str:
        return digest_of(f"{self.phase.value}|{self.status.value}")


class Subtask(StrictModel):
    task_id: str
    run_id: str
    owner_agent: str
    dependencies: list[str] = Field(default_factory=list)
    status: SubtaskStatus = SubtaskStatus.PENDING
    retry_count: int = 0
    input_digest: str


class ConfigSnapshot(StrictModel):
    """运行时不可变的有效配置（脱敏）。历史 Run 靠它回放。"""

    snapshot_id: str
    merged_profile_hash: str
    redacted_content: dict[str, Any]
    created_at: datetime = Field(default_factory=utc_now)


class AgentProfile(StrictModel):
    """agent_kind 是专业分工，不是 RBAC role_id。"""

    agent_id: str
    department: Department
    agent_kind: str
    model_profile_id: str
    skill_bindings: list[str] = Field(default_factory=list)
    mcp_policy_id: str
    capability_policy_id: str


# --------------------------------------------------------------------------
# 证据
# --------------------------------------------------------------------------


class Artifact(StrictModel):
    artifact_id: str
    run_id: str
    type: str
    version: str
    sha256: str
    uri: str
    producer_task_id: str
    trust_level: TrustLevel
    created_at: datetime = Field(default_factory=utc_now)


class ExecutionEvent(StrictModel):
    """追加式审计记录。不可覆盖、不可删除。"""

    event_id: str
    run_id: str
    type: EventType
    actor_id: str
    actor_type: ActorType
    timestamp: datetime = Field(default_factory=utc_now)
    payload_ref: str
    idempotency_key: str
    sequence: int = 0


class ToolExecution(StrictModel):
    """外部副作用与取消对账的唯一依据。"""

    invocation_id: str
    run_id: str
    task_id: str
    tool_name: str
    params_hash: str
    status: ToolExecutionStatus = ToolExecutionStatus.STARTED
    external_operation_id: str | None = None
    idempotency_key: str
    started_at: datetime = Field(default_factory=utc_now)
    settled_at: datetime | None = None


# --------------------------------------------------------------------------
# 缺陷与路由
# --------------------------------------------------------------------------


class Issue(StrictModel):
    """缺陷记录。

    ``routed_department`` / ``routed_leader`` / ``router_policy_version``
    只能由 Router 服务写入，Agent 提交的事件里不允许出现这三个字段
    （见 AgentIssueReport）。
    """

    issue_id: str
    run_id: str
    severity: Severity
    category: IssueCategory
    description: str
    root_cause: IssueCategory | None = None
    evidence_artifact_ids: list[str] = Field(min_length=1)
    status: IssueStatus = IssueStatus.OPEN
    routed_department: Department | None = None
    routed_leader: LeaderRole | None = None
    router_policy_version: str | None = None

    @field_validator("evidence_artifact_ids")
    @classmethod
    def _evidence_not_empty(cls, value: list[str]) -> list[str]:
        if not value:
            raise ValueError("空证据的Issue 不允许存在")
        return value


class RoutingDecision(StrictModel):
    """Router 的确定性输出。仅由服务端 LoopRouter 构造。"""

    source_event_id: str
    issue_id: str
    target_department: Department | None
    target_leader: LeaderRole | None
    reason_code: str
    router_policy_version: str
    evidence_artifact_ids: list[str] = Field(default_factory=list)
    requires_human: bool = False
    secondary_targets: list[LeaderRole] = Field(default_factory=list)


class AgentIssueReport(StrictModel):
    """Agent 可提交的缺陷上报。

    严格禁止 ``target_leader`` / ``routed_leader`` / ``final_gate_result``：
    ``extra="forbid"`` 会在Schema 校验阶段直接拒绝（规范 §7.2 / AC-33）。
    """

    run_id: str
    task_id: str
    type: EventType = EventType.ISSUE_RAISED
    source_agent: str
    artifact_versions: dict[str, str] = Field(default_factory=dict)
    issue: IssueBody
    idempotency_key: str


class IssueBody(StrictModel):
    category: IssueCategory
    root_cause: IssueCategory | None = None
    severity: Severity = Severity.MEDIUM
    description: str
    evidence_artifact_ids: list[str] = Field(min_length=1)


# --------------------------------------------------------------------------
# 澄清与审批
# --------------------------------------------------------------------------


class ClarificationRequest(StrictModel):
    question_id: str
    run_id: str
    phase: RunPhase
    kind: ClarificationKind
    question: str
    context_artifact_ids: list[str] = Field(default_factory=list)
    options: list[str] = Field(default_factory=list)
    required_role: str
    blocking_task_ids: list[str] = Field(default_factory=list)
    input_digest: str
    status: ClarificationStatus = ClarificationStatus.OPEN
    answer: str | None = None
    answered_by: str | None = None
    created_at: datetime = Field(default_factory=utc_now)
    resume_status: RunStatus = RunStatus.RUNNING

    def validate_answer(self, answer: str, moment: datetime) -> None:
        """答复必须绑定当前输入版本，且不能是空默认。"""
        if not answer.strip():
            raise ValueError("澄清答复不能为空")
        if self.status is not ClarificationStatus.OPEN:
            raise ValueError(f"question {self.question_id} 已处于 {self.status.value}")
        if self.created_at > moment:
            raise ValueError("答复时间早于问题创建时间")


class ApprovalRequest(StrictModel):
    """G1 的 Spec/架构人工确认请求。

    仅由 ``ApprovalRequestService.ensure_required`` 幂等创建，
    ``created_by`` 恒为 GATE_EVALUATOR；不存在公开创建入口（规范 §8.4 / REQ-047）。
    """

    approval_id: str
    run_id: str
    gate_id: GateId = GateId.G1
    subject_type: ApprovalSubjectType
    input_digest: str
    request_version: int
    required_roles: list[str]
    expires_at: datetime
    created_by: str
    decision: ApprovalDecision | None = None
    decided_by: str | None = None
    decided_at: datetime | None = None
    decision_reason: str | None = None
    revoked: bool = False
    created_at: datetime = Field(default_factory=utc_now)

    def is_effective(self, moment: datetime) -> bool:
        if self.revoked or self.decision is not ApprovalDecision.APPROVE:
            return False
        if self.expires_at <= moment:
            return False
        return self.decided_at is not None and self.decided_at <= moment

    def apply_decision(
        self,
        decision: ApprovalDecision,
        decided_by: str,
        moment: datetime,
        reason: str | None = None,
    ) -> None:
        if self.revoked:
            raise ValueError(f"approval {self.approval_id} 已撤销")
        if self.decision is not None:
            raise ValueError(f"approval {self.approval_id} 已有决定")
        if self.expires_at <= moment:
            raise ValueError(f"approval {self.approval_id} 已过期")
        self.decision = decision
        self.decided_by = decided_by
        self.decided_at = moment
        self.decision_reason = reason

    def revoke(self, revoked_by: str) -> None:
        self.revoked = True
        self.decision_reason = f"revoked by {revoked_by}"


# --------------------------------------------------------------------------
# 门禁
# --------------------------------------------------------------------------


class GateResult(StrictModel):
    """门禁在特定产物版本、规则版本下的检查记录。"""

    gate_result_id: str
    run_id: str
    gate_id: GateId
    status: GateStatus = GateStatus.NOT_EVALUATED
    policy_version: str
    input_digest: str
    blocker_issue_ids: list[str] = Field(default_factory=list)
    approval_ids: list[str] = Field(default_factory=list)
    deployment_id: str | None = None
    checked_at: datetime | None = None
    evaluated_by: str = "GATE_EVALUATOR"
    commit_sha: str | None = None
    evidence_artifact_id: str | None = None


class GateEvaluationRequest(StrictModel):
    """门禁评估输入。GateEvaluator 只接受结构化输入，不解析 Agent 自由文本。"""

    run_id: str
    gate_id: GateId
    policy_version: str
    input_digest: str
    spec_version: str | None = None
    spec_digest: str | None = None
    product_leader_accepted: StrictBool = False
    product_audit_passed: StrictBool = False
    architecture_digest: str | None = None
    architecture_review_passed: StrictBool = False
    engineering_leader_accepted: StrictBool = False
    required_tests_complete: StrictBool = False
    open_blocking_issue_ids: list[str] = Field(default_factory=list)
    open_nonblocking_issue_ids: list[str] = Field(default_factory=list)
    active_waiver_ids: list[str] = Field(default_factory=list)
    authorization_id: str | None = None
    deployment_id: str | None = None
    target_environment: str | None = None
    artifact_digest: str | None = None
    smoke_check_passed: StrictBool | None = None
    health_check_passed: StrictBool | None = None
    rollback_ready: StrictBool | None = None
    #: 用户在 optional 策略下要求对本 Run 额外确认（§8.4 request-human-approval）
    user_requested_extra_confirmation: StrictBool = False
    risk_triggers: list[str] = Field(default_factory=list)
    evidence_artifact_id: str | None = None

    def as_evidence(self) -> str:
        return self.model_dump_json()


# --------------------------------------------------------------------------
# 测试结果
# --------------------------------------------------------------------------


class ResponsibilitySuggestion(StrictModel):
    agent_id: str
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str


class TestResultReport(StrictModel):
    """Testing Agent 的结构化结论。

    跳过必测、证据缺失一律不得自动 PASS（规范 §7.3）。
    ``responsibility_suggestions`` 不直接派工，必须经Router。
    """

    task_id: str
    agent_id: str
    decision: str = Field(pattern=r"^(PASS|FAIL|INCONCLUSIVE)$")
    commit_sha: str
    test_summary: dict[str, int]
    required_tests_complete: bool
    evidence_artifact_ids: list[str]
    responsibility_suggestions: list[ResponsibilitySuggestion] = Field(
        default_factory=list
    )
    spec_version: str | None = None
    test_plan_version: str | None = None


# --------------------------------------------------------------------------
# 发布与部署
# --------------------------------------------------------------------------


class Release(StrictModel):
    release_id: str
    run_id: str
    project_id: str
    spec_digest: str
    architecture_digest: str
    commit_sha: str
    artifact_digest: str
    g2_gate_result_id: str
    version: str
    status: ReleaseStatus = ReleaseStatus.DRAFT
    created_at: datetime = Field(default_factory=utc_now)


class ReleaseAuthorizationRequest(StrictModel):
    authorization_request_id: str
    release_id: str
    run_id: str
    environment_id: str
    target_ids: list[str] = Field(min_length=1)
    action_scope: list[ReleaseAction] = Field(min_length=1)
    requested_by: str
    request_version: int = Field(default=1, ge=1)
    policy_version: str
    status: AuthorizationRequestStatus = AuthorizationRequestStatus.PENDING
    requested_at: datetime = Field(default_factory=utc_now)
    expires_at: datetime | None = None
    decided_by: str | None = None
    decision_reason: str | None = None

    def targets_digest(self) -> str:
        return digest_of(",".join(sorted(self.target_ids)))


class ReleaseAuthorization(StrictModel):
    """真人批准后签发。绑定 release/环境/目标/产物/时间/次数，不可伪造。"""

    authorization_id: str
    authorization_request_id: str
    release_id: str
    project_id: str
    environment_id: str
    target_ids: list[str]
    artifact_digest: str
    commit_sha: str
    action_scope: list[ReleaseAction] = Field(min_length=1)
    issued_by: str
    issued_at: datetime
    expires_at: datetime
    max_uses: int = Field(ge=1)
    uses: int = 0
    status: AuthorizationStatus = AuthorizationStatus.ACTIVE

    def is_valid_for(
        self,
        moment: datetime,
        release_id: str,
        environment_id: str,
        target_id: str,
        artifact_digest: str,
        action: ReleaseAction,
    ) -> tuple[bool, str]:
        """部署前的完整许可校验。任一条件失败即拒绝。"""
        if self.status is not AuthorizationStatus.ACTIVE:
            return False, f"authorization_status={self.status.value}"
        if self.release_id != release_id:
            return False, "release_id 不匹配"
        if self.environment_id != environment_id:
            return False, "environment_id 不匹配"
        if target_id not in self.target_ids:
            return False, f"target {target_id} 不在授权范围内"
        if self.artifact_digest != artifact_digest:
            return False, "artifact_digest 与授权不匹配"
        if action not in self.action_scope:
            return False, f"action {action.value} 不在授权范围"
        if self.issued_at > moment:
            return False, "许可尚未生效"
        if self.expires_at <= moment:
            return False, "许可已过期"
        if self.uses >= self.max_uses:
            return False, "许可使用次数已耗尽"
        return True, "OK"

    def consume(self) -> None:
        if self.uses >= self.max_uses:
            raise ValueError("许可使用次数已耗尽")
        self.uses += 1
        if self.uses >= self.max_uses:
            self.status = AuthorizationStatus.EXHAUSTED

    def revoke(self) -> None:
        if self.status is AuthorizationStatus.EXHAUSTED:
            return
        self.status = AuthorizationStatus.REVOKED


class Deployment(StrictModel):
    """具体部署尝试。失败重试必须新建尝试与新的 G3 判定。"""

    deployment_id: str
    release_id: str
    run_id: str
    attempt_no: int = Field(ge=1)
    environment_id: str
    target_ids: list[str] = Field(default_factory=list)
    release_artifact_digest: str
    authorization_id: str
    status: DeploymentStatus = DeploymentStatus.PENDING
    reconcile_state: str = "NOT_REQUIRED"
    rollback_operation_id: str | None = None
    gate3_result_id: str | None = None
    external_operation_id: str | None = None


class RiskWaiver(StrictModel):
    """非硬阻断风险的豁免。硬阻断不允许生成 ACTIVE。"""

    waiver_id: str
    run_id: str
    issue_ids: list[str] = Field(min_length=1)
    severity: Severity
    rationale: str
    controls: str
    scope: str
    input_digest: str
    policy_version: str
    requested_by: str
    status: RiskWaiverStatus = RiskWaiverStatus.PENDING
    approved_by: str | None = None
    expires_at: datetime | None = None
    decision_reason: str | None = None
    created_at: datetime = Field(default_factory=utc_now)

    def decide(
        self,
        approve: bool,
        decided_by: str,
        moment: datetime,
        reason: str | None = None,
    ) -> None:
        from .enums import HARD_BLOCKING_SEVERITIES

        if self.status is not RiskWaiverStatus.PENDING:
            raise ValueError(f"waiver {self.waiver_id} 已处于 {self.status.value}")
        if approve and self.severity in HARD_BLOCKING_SEVERITIES:
            raise ValueError(
                f"{self.severity.value} 属于硬性阻断，服务端不允许批准豁免"
            )
        if approve and self.expires_at is not None and self.expires_at <= moment:
            raise ValueError("豁免已过期，不能批准为 ACTIVE")
        self.status = RiskWaiverStatus.ACTIVE if approve else RiskWaiverStatus.REJECTED
        self.approved_by = decided_by
        self.decision_reason = reason

    def is_active_at(self, moment: datetime) -> bool:
        if self.status is not RiskWaiverStatus.ACTIVE:
            return False
        return self.expires_at is None or self.expires_at >= moment


__all__ = [
    "AgentIssueReport",
    "AgentProfile",
    "ApprovalRequest",
    "Artifact",
    "CapabilitySet",
    "ClarificationRequest",
    "ConfigSnapshot",
    "Deployment",
    "ExecutionEvent",
    "GateEvaluationRequest",
    "GateResult",
    "Issue",
    "IssueBody",
    "Principal",
    "Release",
    "ReleaseAuthorization",
    "ReleaseAuthorizationRequest",
    "ResponsibilitySuggestion",
    "RiskWaiver",
    "RoleBinding",
    "RoutingDecision",
    "Run",
    "StrictModel",
    "Subtask",
    "TestResultReport",
    "ToolExecution",
    "digest_of",
    "utc_now",
]
