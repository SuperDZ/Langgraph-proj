"""依据规格白名单穷举 Status 与 GateResult 的迁移及原子拒绝。"""

import pytest

from agentloop.core.contracts.enums import *
from agentloop.core.contracts.models import Run, GateResult, ToolExecution
from agentloop.core.orchestration import InMemoryStore, StateTransitionService, TransitionRejected

pytestmark = [pytest.mark.ac("AC-51"), pytest.mark.requirements("REQ-018", "REQ-042", "REQ-049")]

# 测试预期来自规格 §2.2.2，与实现表独立维护。
STATUS_EDGES = {
    "CREATED": "RUNNING CANCEL_REQUESTED FAILED",
    "RUNNING": "WAITING_GATE WAITING_APPROVAL PAUSED_FOR_HUMAN BLOCKED CANCEL_REQUESTED NEEDS_RECONCILIATION FAILED COMPLETED",
    "WAITING_GATE": "RUNNING WAITING_APPROVAL PAUSED_FOR_HUMAN BLOCKED CANCEL_REQUESTED FAILED",
    "WAITING_APPROVAL": "RUNNING PAUSED_FOR_HUMAN BLOCKED CANCEL_REQUESTED FAILED",
    "PAUSED_FOR_HUMAN": "RUNNING WAITING_GATE WAITING_APPROVAL BLOCKED CANCEL_REQUESTED FAILED",
    "BLOCKED": "RUNNING WAITING_APPROVAL PAUSED_FOR_HUMAN CANCEL_REQUESTED FAILED",
    "CANCEL_REQUESTED": "CANCELLING NEEDS_RECONCILIATION",
    "CANCELLING": "CANCELLED NEEDS_RECONCILIATION",
    "NEEDS_RECONCILIATION": "CANCELLING BLOCKED RUNNING FAILED",
    "FAILED": "", "CANCELLED": "", "COMPLETED": "",
}


@pytest.mark.parametrize("source", list(RunStatus))
@pytest.mark.parametrize("target", list(RunStatus))
def test_status_transition_matrix(source, target):
    store = InMemoryStore()
    service = StateTransitionService(store)
    store.put_run(Run(run_id="r", root_run_id="parent", parent_run_id="parent", run_type=RunType.MAINTENANCE,
        project_id="p", phase=RunPhase.MAINTENANCE, status=source, trigger_source="SYSTEM", config_snapshot_id="s"))
    if target is RunStatus.NEEDS_RECONCILIATION:
        store.put_tool_execution(ToolExecution(invocation_id="tool", run_id="r", task_id="t", tool_name="mock",
            params_hash="x", idempotency_key="tool"))
    allowed = target.value in STATUS_EDGES[source.value].split() or (
        source is target and source not in TERMINAL_RUN_STATUSES)
    before, events = store.get_run("r"), store.all_events()
    if allowed:
        result = service.transition("r", target_status=target, expected_version=before.state_version)
        assert result.status is target
    else:
        with pytest.raises(TransitionRejected):
            service.transition("r", target_status=target, expected_version=before.state_version)
        assert store.get_run("r") == before
        assert store.all_events() == events


@pytest.mark.parametrize("source", list(GateStatus))
@pytest.mark.parametrize("target", list(GateStatus))
def test_gate_transition_matrix(source, target):
    expected = {"NOT_EVALUATED": {"PENDING"}, "PENDING": {"PASSED", "REJECTED", "STALE"},
                "PASSED": {"STALE"}, "REJECTED": set(), "STALE": set()}
    store = InMemoryStore()
    service = StateTransitionService(store)
    gate = GateResult(gate_result_id="g", run_id="r", gate_id=GateId.G1,
                      status=source, input_digest="x", policy_version="v")
    store.put_gate_result(gate)
    if target.value in expected[source.value]:
        assert service.transition_gate(gate, target).status is target
    else:
        with pytest.raises(TransitionRejected):
            service.transition_gate(gate, target)
        assert store.get_gate_result("g") == gate
        assert not store.all_events()


def test_phase_table_matches_authoritative_specification():
    from pathlib import Path
    import re
    from agentloop.core.contracts.transitions import DELIVERY_PHASE_TRANSITIONS
    spec = (Path(__file__).resolve().parents[3] / "notes/multi_agent_loop_platform_design_v1.2.md").read_text(encoding="utf-8")
    table = spec.split("#### 2.2.1", 1)[1].split("#### 2.2.2", 1)[0]
    expected = {}
    for line in table.splitlines():
        match = re.match(r"\| `([A-Z0-9_]+)` \| ([^|]+) \|", line)
        if match:
            expected[RunPhase(match[1])] = frozenset(RunPhase(value) for value in re.findall(r"`([A-Z0-9_]+)`", match[2]))
    assert len(expected) == 13
    assert DELIVERY_PHASE_TRANSITIONS == expected
