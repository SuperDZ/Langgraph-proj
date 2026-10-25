"""三套正交枚举白名单与跨层共享的规范枚举。

依据规范 §0.4 术语、§2.2 正交状态机、§7.1 数据实体、§2.8 权限命名约定。

三条不可混淆的概念线（规范 §2.8）：
- Role：主体身份的职责标签，如 release_approver、operator
- Capability：可执行能力上限，规范前缀 `cap.*`
- ReleaseAction：发布授权允许的操作，枚举 DEPLOY / ROLLBACK

Phase 0 说明：severity 枚举在规范 v1.2 正文中只散落了 P1/HIGH/MEDIUM/LOW
而没有给出完整定义，这里按 v1.2 的阻断语义补齐并集中定义；
P1 与 HIGH 的映射关系在此固化，其他章节按本定义引用。
"""

from __future__ import annotations

from enum import Enum


class RunPhase(str, Enum):
    """Run 当前所处的业务阶段。与 RunStatus 正交，不是运行状态。"""

    INTAKE = "INTAKE"
    PRODUCT = "PRODUCT"
    PRODUCT_AUDIT = "PRODUCT_AUDIT"
    ARCHITECTURE = "ARCHITECTURE"
    G1 = "G1"
    ENGINEERING = "ENGINEERING"
    SECURITY_REVIEW = "SECURITY_REVIEW"
    G2 = "G2"
    RELEASE_AUTHORIZATION = "RELEASE_AUTHORIZATION"
    DEPLOYMENT = "DEPLOYMENT"
    G3 = "G3"
    DEPLOYMENT_RECOVERY = "DEPLOYMENT_RECOVERY"
    DELIVERY = "DELIVERY"
    # 子 Run 专用阶段
    MAINTENANCE = "MAINTENANCE"
    INCIDENT = "INCIDENT_RESPONSE"
    RETROSPECTIVE = "RETROSPECTIVE"


class RunStatus(str, Enum):
    """Run 的运行状态。与 RunPhase 正交。终态不可复活。"""

    CREATED = "CREATED"
    RUNNING = "RUNNING"
    WAITING_GATE = "WAITING_GATE"
    PAUSED_FOR_HUMAN = "PAUSED_FOR_HUMAN"
    WAITING_APPROVAL = "WAITING_APPROVAL"
    BLOCKED = "BLOCKED"
    CANCEL_REQUESTED = "CANCEL_REQUESTED"
    CANCELLING = "CANCELLING"
    NEEDS_RECONCILIATION = "NEEDS_RECONCILIATION"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    COMPLETED = "COMPLETED"


class GateStatus(str, Enum):
    """单次门禁判定的状态。每次重新评估都新建一条 GateResult，不复用旧记录。"""

    NOT_EVALUATED = "NOT_EVALUATED"
    PENDING = "PENDING"
    PASSED = "PASSED"
    REJECTED = "REJECTED"
    STALE = "STALE"


class GateId(str, Enum):
    G1 = "G1"
    G2 = "G2"
    G3 = "G3"


class RunType(str, Enum):
    DELIVERY = "DELIVERY"
    MAINTENANCE = "MAINTENANCE"
    INCIDENT = "INCIDENT"
    RETROSPECTIVE = "RETROSPECTIVE"


class SubtaskStatus(str, Enum):
    PENDING = "PENDING"
    READY = "READY"
    RUNNING = "RUNNING"
    FAILED = "FAILED"
    BLOCKED = "BLOCKED"
    CANCELLED = "CANCELLED"
    DONE = "DONE"


class Severity(str, Enum):
    """缺陷/风险严重性。

    v1.2 的 G2 放行条件与风险豁免规则直接依赖本枚举：
    - CRITICAL（P1）与 HIGH（严重安全漏洞）为硬性阻断，不允许生成 ACTIVE 豁免
    - MEDIUM / LOW 为非硬阻断，可按政策申请有期限豁免
    """

    CRITICAL = "CRITICAL"
    HIGH = "HIGH"
    MEDIUM = "MEDIUM"
    LOW = "LOW"
    INFO = "INFO"


#: 硬性阻断严重性。服务端不允许为其生成 ACTIVE 豁免（规范 §2.8 / REQ-013）。
HARD_BLOCKING_SEVERITIES: frozenset[Severity] = frozenset(
    {Severity.CRITICAL, Severity.HIGH}
)


class IssueCategory(str, Enum):
    """规范 §2.7 的规范 category，取值决定责任归属。"""

    SPEC_DEFECT = "SPEC_DEFECT"
    UX_DEFECT = "UX_DEFECT"
    ARCH_DEFECT = "ARCH_DEFECT"
    CODE_DEFECT = "CODE_DEFECT"
    TEST_DEFECT = "TEST_DEFECT"
    SECURITY_FINDING = "SECURITY_FINDING"
    DEPLOY_FAILURE = "DEPLOY_FAILURE"
    ENV_DEFECT = "ENV_DEFECT"
    MERGE_CONFLICT = "MERGE_CONFLICT"
    UNCLASSIFIED = "UNCLASSIFIED"


class IssueStatus(str, Enum):
    OPEN = "OPEN"
    ROUTED = "ROUTED"
    ACKNOWLEDGED = "ACKNOWLEDGED"
    RESOLVED = "RESOLVED"
    REJECTED = "REJECTED"


class Department(str, Enum):
    PRODUCT = "product"
    ENGINEERING = "engineering"
    EXPERT = "expert"


class LeaderRole(str, Enum):
    PRODUCT_LEADER = "product-leader"
    EXPERT_LEADER = "expert-leader"
    ENGINEERING_LEADER = "engineering-leader"


class PrincipalType(str, Enum):
    HUMAN_USER = "human_user"
    AGENT_SERVICE = "agent_service"
    SYSTEM_SERVICE = "system_service"


class ReleaseAction(str, Enum):
    """发布授权允许的操作。统一大写，禁止与 cap.* 或 role 混用。"""

    DEPLOY = "DEPLOY"
    ROLLBACK = "ROLLBACK"


class ReleaseStatus(str, Enum):
    DRAFT = "DRAFT"
    READY = "READY"
    DEPLOYING = "DEPLOYING"
    DEPLOYED = "DEPLOYED"
    INVALIDATED = "INVALIDATED"
    ABANDONED = "ABANDONED"


class AuthorizationRequestStatus(str, Enum):
    PENDING = "PENDING"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    EXPIRED = "EXPIRED"
    CANCELLED = "CANCELLED"


class AuthorizationStatus(str, Enum):
    ACTIVE = "ACTIVE"
    EXPIRED = "EXPIRED"
    REVOKED = "REVOKED"
    EXHAUSTED = "EXHAUSTED"


class DeploymentStatus(str, Enum):
    PENDING = "PENDING"
    IN_PROGRESS = "IN_PROGRESS"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    ROLLING_BACK = "ROLLING_BACK"
    ROLLED_BACK = "ROLLED_BACK"
    UNKNOWN = "UNKNOWN"


class ReconcileState(str, Enum):
    NOT_REQUIRED = "NOT_REQUIRED"
    PENDING = "PENDING"
    SAFE_ROLLED_BACK = "SAFE_ROLLED_BACK"
    RECOVERED = "RECOVERED"
    UNKNOWN = "UNKNOWN"
    MANUAL_REQUIRED = "MANUAL_REQUIRED"


class RiskWaiverStatus(str, Enum):
    PENDING = "PENDING"
    ACTIVE = "ACTIVE"
    REJECTED = "REJECTED"
    REVOKED = "REVOKED"
    EXPIRED = "EXPIRED"


class ApprovalSubjectType(str, Enum):
    SPEC = "SPEC"
    ARCHITECTURE = "ARCHITECTURE"


class ApprovalDecision(str, Enum):
    APPROVE = "APPROVE"
    REJECT = "REJECT"


class ClarificationStatus(str, Enum):
    OPEN = "OPEN"
    ANSWERED = "ANSWERED"
    CANCELLED = "CANCELLED"


class ClarificationKind(str, Enum):
    MISSING_REQUIREMENT = "MISSING_REQUIREMENT"
    CONFLICTING_CONSTRAINTS = "CONFLICTING_CONSTRAINTS"
    BUSINESS_DECISION = "BUSINESS_DECISION"
    MISSING_TARGET_SCOPE = "MISSING_TARGET_SCOPE"
    EXPLICIT_CONFIRMATION_REQUEST = "EXPLICIT_CONFIRMATION_REQUEST"
    AMBIGUOUS_OWNERSHIP = "AMBIGUOUS_OWNERSHIP"


class HumanApprovalMode(str, Enum):
    """human_approval.spec / human_approval.architecture 的取值。"""

    DISABLED = "disabled"
    OPTIONAL = "optional"
    REQUIRED = "required"


class TrustLevel(str, Enum):
    """Artifact 的可信级别。不可信产物不可直接当作事实或指令。"""

    TRUSTED_FIRST_PARTY = "trusted_first_party"
    VERIFIED_INTERNAL = "verified_internal"
    UNTRUSTED_EXTERNAL = "untrusted_external"
    MODEL_GENERATED = "model_generated"
    USER_SUPPLIED = "user_supplied"


class ToolExecutionStatus(str, Enum):
    STARTED = "STARTED"
    SUCCEEDED = "SUCCEEDED"
    FAILED = "FAILED"
    PARTIALLY_COMMITTED = "PARTIALLY_COMMITTED"
    UNKNOWN = "UNKNOWN"
    COMPENSATED = "COMPENSATED"
    CANCELLED = "CANCELLED"


class EventType(str, Enum):
    """追加式审计事件类型。不可覆盖、不可删除。"""

    RUN_CREATED = "RUN_CREATED"
    RUN_PHASE_CHANGED = "RUN_PHASE_CHANGED"
    RUN_STATUS_CHANGED = "RUN_STATUS_CHANGED"
    RUN_STATE_VERSION_CONFLICT = "RUN_STATE_VERSION_CONFLICT"
    INVALID_TRANSITION_REJECTED = "INVALID_TRANSITION_REJECTED"
    GATE_EVALUATION_STARTED = "GATE_EVALUATION_STARTED"
    GATE_RESULT_RECORDED = "GATE_RESULT_RECORDED"
    GATE_RESULT_INVALIDATED = "GATE_RESULT_INVALIDATED"
    APPROVAL_REQUEST_CREATED = "APPROVAL_REQUEST_CREATED"
    APPROVAL_REQUEST_DECIDED = "APPROVAL_REQUEST_DECIDED"
    APPROVAL_REQUEST_REVOKED = "APPROVAL_REQUEST_REVOKED"
    CLARIFICATION_REQUESTED = "CLARIFICATION_REQUESTED"
    CLARIFICATION_ANSWERED = "CLARIFICATION_ANSWERED"
    ISSUE_RAISED = "ISSUE_RAISED"
    ISSUE_ROUTED = "ISSUE_ROUTED"
    ACCESS_DENIED = "ACCESS_DENIED"
    UNTRUSTED_INSTRUCTION_DETECTED = "UNTRUSTED_INSTRUCTION_DETECTED"
    RELEASE_CREATED = "RELEASE_CREATED"
    RELEASE_AUTHORIZATION_REQUESTED = "RELEASE_AUTHORIZATION_REQUESTED"
    RELEASE_AUTHORIZATION_DECIDED = "RELEASE_AUTHORIZATION_DECIDED"
    RELEASE_AUTHORIZATION_REVOKED = "RELEASE_AUTHORIZATION_REVOKED"
    DEPLOYMENT_ATTEMPTED = "DEPLOYMENT_ATTEMPTED"
    DEPLOYMENT_RESULT_RECORDED = "DEPLOYMENT_RESULT_RECORDED"
    RECONCILIATION_RECORDED = "RECONCILIATION_RECORDED"
    WORKER_OUTPUT_RECORDED = "WORKER_OUTPUT_RECORDED"
    DEPARTMENT_ACCEPTED = "DEPARTMENT_ACCEPTED"
    CHECK_TRIGGERED = "CHECK_TRIGGERED"
    TEST_EXECUTED = "TEST_EXECUTED"
    LOCAL_REWORK = "LOCAL_REWORK"
    EXTERNAL_REWORK = "EXTERNAL_REWORK"
    ISSUE_RESOLVED = "ISSUE_RESOLVED"
    BASELINE_CHANGED = "BASELINE_CHANGED"
    RUNTIME_AUDIT = "RUNTIME_AUDIT"


class ActorType(str, Enum):
    HUMAN = "HUMAN"
    AGENT = "AGENT"
    SYSTEM = "SYSTEM"


TERMINAL_RUN_STATUSES: frozenset[RunStatus] = frozenset(
    {RunStatus.FAILED, RunStatus.CANCELLED, RunStatus.COMPLETED}
)

TERMINAL_GATE_STATUSES: frozenset[GateStatus] = frozenset(
    {GateStatus.REJECTED, GateStatus.STALE}
)

#: 需要人工审批介入的阶段。
GATE_PHASES: frozenset[RunPhase] = frozenset(
    {RunPhase.G1, RunPhase.G2, RunPhase.G3}
)

#: 评估待决阶段允许的运行状态集合（规范 §2.2.2 组合守卫最低集合）。
GATE_EVALUATING_STATUSES: frozenset[RunStatus] = frozenset(
    {RunStatus.WAITING_GATE, RunStatus.WAITING_APPROVAL, RunStatus.RUNNING}
)

#: DEPLOYMENT_RECOVERY 阶段允许的状态集合（规范 §2.2.2 组合守卫）。
RECOVERY_ALLOWED_STATUSES: frozenset[RunStatus] = frozenset(
    {
        RunStatus.RUNNING,
        RunStatus.BLOCKED,
        RunStatus.NEEDS_RECONCILIATION,
        RunStatus.CANCEL_REQUESTED,
        RunStatus.CANCELLING,
        RunStatus.CANCELLED,
        RunStatus.FAILED,
    }
)

#: 阶段内允许停留、不需要迁移的情况：内部 Worker Loop、等待、重试 Gate、整改。
SELF_TRANSITION_ALLOWED: frozenset[RunStatus] = frozenset(
    {
        RunStatus.WAITING_GATE,
        RunStatus.WAITING_APPROVAL,
        RunStatus.PAUSED_FOR_HUMAN,
        RunStatus.BLOCKED,
        RunStatus.RUNNING,
        RunStatus.NEEDS_RECONCILIATION,
    }
)
