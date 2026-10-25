"""AC-32 / AC-46 / AC-51：三套正交状态机的穷举校验。

关联需求：REQ-018、REQ-042、REQ-049。
断言对象：持久化状态与事件记录，不是任何模型输出文本。
"""

from __future__ import annotations

import pytest

from agentloop.core.contracts.enums import (
    ActorType,
    EventType,
    GateId,
    GateStatus,
    RunPhase,
    RunStatus,
    RunType,
)
from agentloop.core.contracts.models import GateResult, Run
from agentloop.core.contracts.transitions import (
    DELIVERY_PHASE_TRANSITIONS,
    GATE_STATUS_TRANSITIONS,
    RUN_STATUS_TRANSITIONS,
    check_composite_guard,
)
from agentloop.core.orchestration import InMemoryStore, StateTransitionService, TransitionRejected

pytestmark = [pytest.mark.ac("AC-32"), pytest.mark.ac("AC-46"), pytest.mark.ac("AC-51")]


def test_ac32_phase_and_status_are_independent_enums(store: InMemoryStore):
    """AC-32：相同 status、不同 phase 时两套枚举独立存储且可分别查询。

    对应 REQ-018：Phase、Status 和 GateResult 状态彼此独立。
    """
    store.put_run(
        Run(
            run_id="r-a",
            run_type=RunType.DELIVERY,
            project_id="p",
            phase=RunPhase.G1,
            status=RunStatus.WAITING_APPROVAL,
            trigger_source="USER",
            config_snapshot_id="s",
        )
    )
    store.put_run(
        Run(
            run_id="r-b",
            run_type=RunType.DELIVERY,
            project_id="p",
            phase=RunPhase.G2,
            status=RunStatus.WAITING_APPROVAL,
            trigger_source="USER",
            config_snapshot_id="s",
        )
    )

    a = store.get_run("r-a")
    b = store.get_run("r-b")

    assert a.status is b.status is RunStatus.WAITING_APPROVAL
    assert a.phase is RunPhase.G1 and b.phase is RunPhase.G2
    assert a.version_digest() != b.version_digest()


def test_ac46_cannot_complete_while_gate_pending(transitions, store):
    """AC-46：G3 仍 PENDING 时把 Run 标记为 COMPLETED 必须被拒绝。

    对应 REQ-018。断言：抛出 409 且原状态不变。
    """
    run = transitions.create_run(
        run_id="run-x",
        run_type=RunType.DELIVERY,
        project_id="p",
        trigger_source="USER",
        config_snapshot_id="s",
    )
    transitions.transition("run-x", target_status=RunStatus.RUNNING)
    seeded = store.get_run("run-x")
    seeded.phase = RunPhase.G3
    store.put_run(seeded)

    store.put_gate_result(
        GateResult(
            gate_result_id="g3-1",
            run_id="run-x",
            gate_id=GateId.G3,
            status=GateStatus.PENDING,
            policy_version="gate-policy-v1.2",
            input_digest="sha256:abc",
        )
    )

    current = store.get_run("run-x")
    with pytest.raises(TransitionRejected):
        transitions.advance_to_delivery("run-x", expected_version=current.state_version)

    after = store.get_run("run-x")
    assert after.status is RunStatus.RUNNING, "非法跃迁不得改变原状态"
    assert after.phase is RunPhase.G3
    assert after.state_version == current.state_version, "失败不能部分落库"
    assert store.count_events_of_type(EventType.GATE_RESULT_RECORDED, "run-x") == 0


def test_ac51_exhaustive_phase_whitelist(transitions):
    """AC-51：穷举 phase 白名单，只接受表内合法跃迁。

    对应 REQ-042、REQ-049。
    """
    store = transitions.store
    store.put_run(
        Run(
            run_id="run-e",
            run_type=RunType.DELIVERY,
            project_id="p",
            phase=RunPhase.INTAKE,
            status=RunStatus.RUNNING,
            trigger_source="USER",
            config_snapshot_id="s",
        )
    )

    original = store.get_run("run-e")
    accepted, rejected = [], []
    for target in RunPhase:
        if target is RunPhase.INTAKE:
            continue  # 允许原地等待，不是跨阶段边
        store.put_run(original)
        version = store.get_run("run-e").state_version
        try:
            transitions.transition(
                "run-e", target_phase=target, expected_version=version
            )
            accepted.append(target)
        except TransitionRejected:
            rejected.append(target)

    expected = DELIVERY_PHASE_TRANSITIONS[RunPhase.INTAKE]
    assert set(accepted) == set(expected), "接受集合必须精确等于白名单"
    assert RunPhase.PRODUCT in accepted
    assert RunPhase.DELIVERY in rejected, "DELIVERY 不能从 INTAKE 直达"
    assert RunPhase.G2 in rejected


def test_ac51_terminal_status_cannot_revive(transitions):
    """AC-51：终态不可复活。"""
    store = transitions.store
    store.put_run(
        Run(
            run_id="run-t",
            run_type=RunType.DELIVERY,
            project_id="p",
            phase=RunPhase.DELIVERY,
            status=RunStatus.FAILED,
            trigger_source="USER",
            config_snapshot_id="s",
        )
    )
    for target in RunStatus:
        with pytest.raises(TransitionRejected):
            transitions.transition("run-t", target_status=target)

    assert store.get_run("run-t").status is RunStatus.FAILED
    assert RUN_STATUS_TRANSITIONS[RunStatus.FAILED] == frozenset()


def test_ac51_gate_result_whitelist_is_terminal_after_reject(transitions, store):
    """AC-51：REJECTED / STALE 的GateResult 不可恢复。"""
    rejected = GateResult(
        gate_result_id="g-1",
        run_id="run-g",
        gate_id=GateId.G2,
        status=GateStatus.NOT_EVALUATED,
        policy_version="v1",
        input_digest="sha256:x",
    )
    transitions.transition_gate(rejected, GateStatus.PENDING)
    result = transitions.transition_gate(store.get_gate_result("g-1"), GateStatus.REJECTED)

    for target in (GateStatus.PENDING, GateStatus.PASSED, GateStatus.STALE):
        with pytest.raises(TransitionRejected):
            transitions.transition_gate(result, target)

    assert store.get_gate_result("g-1").status is GateStatus.REJECTED
    assert GATE_STATUS_TRANSITIONS[GateStatus.REJECTED] == frozenset()


def test_ac51_composite_guard_blocks_gate_with_created_status():
    """AC-51：phase 与 status 必须按复合守卫共同检查，不能各自通过即放行。

    场景：BLOCKED 不是 G1/G2/G3 评估待决时的合法状态。
    """
    violation = check_composite_guard(
        RunType.DELIVERY, RunPhase.G2, RunStatus.CREATED
    )
    assert violation is not None
    assert violation.code == "INVALID_COMBINATION"
    assert "G2" in violation.message


def test_ac51_recovery_phase_accepts_only_recovery_statuses():
    """AC-51：DEPLOYMENT_RECOVERY 只接受恢复相关状态。"""
    for status in RunStatus:
        violation = check_composite_guard(
            RunType.DELIVERY, RunPhase.DEPLOYMENT_RECOVERY, status
        )
        if status in {
            RunStatus.RUNNING,
            RunStatus.BLOCKED,
            RunStatus.NEEDS_RECONCILIATION,
            RunStatus.CANCEL_REQUESTED,
            RunStatus.CANCELLING,
            RunStatus.CANCELLED,
            RunStatus.FAILED,
        }:
            assert violation is None, f"{status.value} 应被接受"
        else:
            assert violation is not None, f"{status.value} 应被拒绝"


def test_ac51_concurrent_state_version_conflict_preserves_state(transitions, store):
    """AC-51：并发 CAS 冲突返回错误且事件/状态不变。"""
    store.put_run(
        Run(
            run_id="run-c",
            run_type=RunType.DELIVERY,
            project_id="p",
            phase=RunPhase.INTAKE,
            status=RunStatus.RUNNING,
            trigger_source="USER",
            config_snapshot_id="s",
        )
    )
    stale_version = store.get_run("run-c").state_version

    # 第一个工作线程成功推进
    transitions.transition(
        "run-c", target_phase=RunPhase.PRODUCT, expected_version=stale_version
    )

    # 第二个工作线程拿着过期的 state_version
    with pytest.raises(TransitionRejected) as excinfo:
        transitions.transition(
            "run-c", target_phase=RunPhase.PRODUCT_AUDIT, expected_version=stale_version
        )

    assert excinfo.value.code == "STATE_VERSION_CONFLICT"
    after = store.get_run("run-c")
    assert after.phase is RunPhase.PRODUCT, "冲突不得覆盖先写"
    assert store.count_events_of_type(EventType.RUN_STATE_VERSION_CONFLICT, "run-c") == 0


def test_ac51_g1_rejection_routes_to_upstream_phases(transitions, store):
    """AC-51 / REQ-049：G1 驳回分支必须返回合法阶段。

    G1 允许退 PRODUCT 或 ARCHITECTURE，退 ENGINEERING 是非法的。
    """
    store.put_run(
        Run(
            run_id="run-g1",
            run_type=RunType.DELIVERY,
            project_id="p",
            phase=RunPhase.G1,
            status=RunStatus.RUNNING,
            trigger_source="USER",
            config_snapshot_id="s",
        )
    )
    version = store.get_run("run-g1").state_version
    updated = transitions.transition(
        "run-g1", target_phase=RunPhase.PRODUCT, expected_version=version
    )
    assert updated.phase is RunPhase.PRODUCT

    with pytest.raises(TransitionRejected):
        version2 = store.get_run("run-g1").state_version
        transitions.transition(
            "run-g1",
            target_phase=RunPhase.ENGINEERING,
            expected_version=version2,
        )


def test_ac51_delivery_is_the_only_successful_terminal():
    """DELIVERY 是唯一成功终点：只有 G3 阶段可进入，且无任何出口。"""
    assert DELIVERY_PHASE_TRANSITIONS[RunPhase.DELIVERY] == frozenset()

    with_delivery_exit = {
        phase for phase, targets in DELIVERY_PHASE_TRANSITIONS.items()
        if RunPhase.DELIVERY in targets
    }
    assert with_delivery_exit == {RunPhase.G3}, "只有 G3 可通往 DELIVERY"
