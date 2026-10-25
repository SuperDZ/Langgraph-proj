"""编排层：生命周期、状态机、质量门禁。"""

from .state_transition import StateTransitionService, TransitionRejected
from .store import ConcurrentModificationError, InMemoryStore


def __getattr__(name):
    # 审批服务依赖存储；延迟导出门禁，避免审批与门禁互相导入。
    if name in {"GATE_POLICY_VERSION", "GateEvaluator"}:
        from . import gate_evaluator
        return getattr(gate_evaluator, name)
    if name == "SQLiteStore":
        from .sqlite_store import SQLiteStore
        return SQLiteStore
    raise AttributeError(name)

__all__ = [
    "GATE_POLICY_VERSION",
    "ConcurrentModificationError",
    "GateEvaluator",
    "InMemoryStore",
    "SQLiteStore",
    "StateTransitionService",
    "TransitionRejected",
]
