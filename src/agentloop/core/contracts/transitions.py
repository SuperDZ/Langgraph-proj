"""Phase / Status / GateResult 三套正交迁移白名单。

数据来源（规范 v1.2）：
- §2.2.1 DELIVERY Run 阶段迁移白名单
- §2.2.2 Run.status 迁移白名单
- §2.2.3 GateResult.status 独立迁移白名单
- §2.2.4 G3 失败后恢复状态的确定性决策

白名单是纯数据，便于单测穷举；任何不在表内的跃迁一律拒绝。
"""

from __future__ import annotations

from .enums import (
    GATE_PHASES,
    GATE_EVALUATING_STATUSES,
    RECOVERY_ALLOWED_STATUSES,
    TERMINAL_GATE_STATUSES,
    TERMINAL_RUN_STATUSES,
    GateId,
    GateStatus,
    RunPhase,
    RunStatus,
    RunType,
)

# --------------------------------------------------------------------------
# §2.2.1 DELIVERY Run 阶段迁移白名单
# --------------------------------------------------------------------------

DELIVERY_PHASE_TRANSITIONS: dict[RunPhase, frozenset[RunPhase]] = {
    RunPhase.INTAKE: frozenset({RunPhase.PRODUCT}),
    RunPhase.PRODUCT: frozenset({RunPhase.PRODUCT_AUDIT}),
    RunPhase.PRODUCT_AUDIT: frozenset({RunPhase.PRODUCT, RunPhase.ARCHITECTURE}),
    RunPhase.ARCHITECTURE: frozenset({RunPhase.PRODUCT, RunPhase.G1}),
    RunPhase.G1: frozenset(
        {RunPhase.PRODUCT, RunPhase.ARCHITECTURE, RunPhase.ENGINEERING}
    ),
    RunPhase.ENGINEERING: frozenset(
        {RunPhase.PRODUCT, RunPhase.ARCHITECTURE, RunPhase.SECURITY_REVIEW}
    ),
    RunPhase.SECURITY_REVIEW: frozenset(
        {
            RunPhase.G2,
            RunPhase.ENGINEERING,
            RunPhase.PRODUCT,
            RunPhase.ARCHITECTURE,
        }
    ),
    RunPhase.G2: frozenset(
        {
            RunPhase.ENGINEERING,
            RunPhase.PRODUCT,
            RunPhase.ARCHITECTURE,
            RunPhase.RELEASE_AUTHORIZATION,
        }
    ),
    RunPhase.RELEASE_AUTHORIZATION: frozenset(
        {
            RunPhase.DEPLOYMENT,
            RunPhase.ENGINEERING,
            RunPhase.PRODUCT,
            RunPhase.ARCHITECTURE,
        }
    ),
    RunPhase.DEPLOYMENT: frozenset(
        {RunPhase.G3, RunPhase.DEPLOYMENT_RECOVERY}
    ),
    RunPhase.G3: frozenset({RunPhase.DELIVERY, RunPhase.DEPLOYMENT_RECOVERY}),
    RunPhase.DEPLOYMENT_RECOVERY: frozenset(
        {
            RunPhase.RELEASE_AUTHORIZATION,
            RunPhase.ENGINEERING,
            RunPhase.PRODUCT,
            RunPhase.ARCHITECTURE,
        }
    ),
    RunPhase.DELIVERY: frozenset(),
}

# --------------------------------------------------------------------------
# 子 Run 阶段迁移白名单
#
# v1.2 正文只定义了 DELIVERY Run 的阶段迁移表（规范 §2.2.1），
# 但 REQ-042 要求 Phase 使用"完整可机测白名单"。这里按子 Run 的
# 专属终止条件补齐，使 AC-51 的穷举检查不留空白。
# 依据：§2.9 子 Run 使用独立 run_id、预算、状态与 checkpoint；
#       §10.7 运维子 Run 不得修改父交付 Run 状态。
# --------------------------------------------------------------------------

MAINTENANCE_PHASE_TRANSITIONS: dict[RunPhase, frozenset[RunPhase]] = {
    RunPhase.INTAKE: frozenset({RunPhase.MAINTENANCE}),
    RunPhase.MAINTENANCE: frozenset(),  # 终态阶段，终止条件由 RunStatus=COMPLETED 表达
}

INCIDENT_PHASE_TRANSITIONS: dict[RunPhase, frozenset[RunPhase]] = {
    RunPhase.INTAKE: frozenset({RunPhase.INCIDENT}),
    RunPhase.INCIDENT: frozenset(),  # 安全/跨部门问题经 Router 转交责任 Leader，由父 Run 承接整改
}

RETROSPECTIVE_PHASE_TRANSITIONS: dict[RunPhase, frozenset[RunPhase]] = {
    RunPhase.INTAKE: frozenset({RunPhase.RETROSPECTIVE}),
    RunPhase.RETROSPECTIVE: frozenset(),
}

PHASE_TRANSITIONS: dict[RunType, dict[RunPhase, frozenset[RunPhase]]] = {
    RunType.DELIVERY: DELIVERY_PHASE_TRANSITIONS,
    RunType.MAINTENANCE: MAINTENANCE_PHASE_TRANSITIONS,
    RunType.INCIDENT: INCIDENT_PHASE_TRANSITIONS,
    RunType.RETROSPECTIVE: RETROSPECTIVE_PHASE_TRANSITIONS,
}

# --------------------------------------------------------------------------
# §2.2.2 Run.status 迁移白名单
# --------------------------------------------------------------------------

RUN_STATUS_TRANSITIONS: dict[RunStatus, frozenset[RunStatus]] = {
    RunStatus.CREATED: frozenset(
        {RunStatus.RUNNING, RunStatus.CANCEL_REQUESTED, RunStatus.FAILED}
    ),
    RunStatus.RUNNING: frozenset(
        {
            RunStatus.WAITING_GATE,
            RunStatus.WAITING_APPROVAL,
            RunStatus.PAUSED_FOR_HUMAN,
            RunStatus.BLOCKED,
            RunStatus.CANCEL_REQUESTED,
            RunStatus.NEEDS_RECONCILIATION,
            RunStatus.FAILED,
            RunStatus.COMPLETED,
        }
    ),
    RunStatus.WAITING_GATE: frozenset(
        {
            RunStatus.RUNNING,
            RunStatus.WAITING_APPROVAL,
            RunStatus.PAUSED_FOR_HUMAN,
            RunStatus.BLOCKED,
            RunStatus.CANCEL_REQUESTED,
            RunStatus.FAILED,
        }
    ),
    RunStatus.WAITING_APPROVAL: frozenset(
        {
            RunStatus.RUNNING,
            RunStatus.PAUSED_FOR_HUMAN,
            RunStatus.BLOCKED,
            RunStatus.CANCEL_REQUESTED,
            RunStatus.FAILED,
        }
    ),
    RunStatus.PAUSED_FOR_HUMAN: frozenset(
        {
            RunStatus.RUNNING,
            RunStatus.WAITING_GATE,
            RunStatus.WAITING_APPROVAL,
            RunStatus.BLOCKED,
            RunStatus.CANCEL_REQUESTED,
            RunStatus.FAILED,
        }
    ),
    RunStatus.BLOCKED: frozenset(
        {
            RunStatus.RUNNING,
            RunStatus.WAITING_APPROVAL,
            RunStatus.PAUSED_FOR_HUMAN,
            RunStatus.CANCEL_REQUESTED,
            RunStatus.FAILED,
        }
    ),
    RunStatus.CANCEL_REQUESTED: frozenset(
        {RunStatus.CANCELLING, RunStatus.NEEDS_RECONCILIATION}
    ),
    RunStatus.CANCELLING: frozenset(
        {RunStatus.CANCELLED, RunStatus.NEEDS_RECONCILIATION}
    ),
    RunStatus.NEEDS_RECONCILIATION: frozenset(
        {
            RunStatus.CANCELLING,
            RunStatus.BLOCKED,
            RunStatus.RUNNING,
            RunStatus.FAILED,
        }
    ),
    RunStatus.FAILED: frozenset(),
    RunStatus.CANCELLED: frozenset(),
    RunStatus.COMPLETED: frozenset(),
}

# --------------------------------------------------------------------------
# §2.2.3 GateResult.status 独立迁移白名单
# --------------------------------------------------------------------------

GATE_STATUS_TRANSITIONS: dict[GateStatus, frozenset[GateStatus]] = {
    GateStatus.NOT_EVALUATED: frozenset({GateStatus.PENDING}),
    GateStatus.PENDING: frozenset(
        {GateStatus.PASSED, GateStatus.REJECTED, GateStatus.STALE}
    ),
    # 等待人工确认时保持 PENDING，不写入新状态
    GateStatus.PASSED: frozenset({GateStatus.STALE}),
    GateStatus.REJECTED: frozenset(),
    GateStatus.STALE: frozenset(),
}

# --------------------------------------------------------------------------
# §2.2.2 组合守卫（最低集合）
# --------------------------------------------------------------------------


class GuardViolation:
    """组合守卫违规。构造非法状态的请求会返回这个而不是静默放行。"""

    def __init__(self, code: str, message: str) -> None:
        self.code = code
        self.message = message

    def __repr__(self) -> str:  # pragma: no cover - 调试辅助
        return f"GuardViolation({self.code}, {self.message!r})"


def check_composite_guard(
    run_type: RunType,
    phase: RunPhase,
    status: RunStatus,
) -> GuardViolation | None:
    """phase 与 status 必须按复合守卫共同检查，而不是各自通过即放行。"""
    if phase not in PHASE_TRANSITIONS[run_type]:
        return GuardViolation("INVALID_COMBINATION", "phase 不属于该 Run 类型")

    if phase is RunPhase.DELIVERY and status is not RunStatus.COMPLETED:
        return GuardViolation("INVALID_COMBINATION", "DELIVERY 必须原子地处于 COMPLETED")

    if phase in GATE_PHASES and status not in GATE_EVALUATING_STATUSES | {
        RunStatus.PAUSED_FOR_HUMAN, RunStatus.BLOCKED, RunStatus.CANCEL_REQUESTED,
        RunStatus.CANCELLING, RunStatus.CANCELLED, RunStatus.FAILED,
    }:
        return GuardViolation(
            "INVALID_COMBINATION",
            f"phase={phase.value} 评估待决时 status 必须是 "
            f"{sorted(s.value for s in GATE_EVALUATING_STATUSES)}，"
            f"当前为 {status.value}",
        )

    if phase is RunPhase.DEPLOYMENT_RECOVERY and status not in RECOVERY_ALLOWED_STATUSES:
        return GuardViolation(
            "INVALID_COMBINATION",
            f"phase=DEPLOYMENT_RECOVERY 不接受 status={status.value}",
        )

    return None


def is_terminal_status(status: RunStatus) -> bool:
    return status in TERMINAL_RUN_STATUSES


def is_terminal_gate_status(status: GateStatus) -> bool:
    return status in TERMINAL_GATE_STATUSES


def allowed_phase_targets(run_type: RunType, phase: RunPhase) -> frozenset[RunPhase]:
    table = PHASE_TRANSITIONS.get(run_type)
    if table is None:
        return frozenset()
    return table.get(phase, frozenset())


def phase_table_for(run_type: RunType) -> dict[RunPhase, frozenset[RunPhase]]:
    return PHASE_TRANSITIONS.get(run_type, {})


__all__ = [
    "DELIVERY_PHASE_TRANSITIONS",
    "GATE_STATUS_TRANSITIONS",
    "GATE_EVALUATING_STATUSES",
    "GuardViolation",
    "INCIDENT_PHASE_TRANSITIONS",
    "MAINTENANCE_PHASE_TRANSITIONS",
    "PHASE_TRANSITIONS",
    "RETROSPECTIVE_PHASE_TRANSITIONS",
    "RUN_STATUS_TRANSITIONS",
    "allowed_phase_targets",
    "check_composite_guard",
    "is_terminal_gate_status",
    "is_terminal_status",
    "phase_table_for",
]
