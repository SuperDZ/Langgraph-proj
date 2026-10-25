"""真实 SQLite Checkpointer、进程重启及原子故障注入。"""

import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

from agentloop.core.contracts.enums import *
from agentloop.core.orchestration import SQLiteStore, StateTransitionService, TransitionRejected
from agentloop.core.approvals import RBACService

pytestmark = [pytest.mark.requirements("REQ-006", "REQ-033", "REQ-039", "REQ-040", "REQ-042")]


def cli(tmp_path, command, *extra):
    root = Path(__file__).resolve().parents[2]
    env = {**os.environ, "PYTHONPATH": str(root), "LANGSMITH_TRACING": "false"}
    completed = subprocess.run([sys.executable, "-m", "agentloop", command,
        "--data-dir", str(tmp_path), *extra], env=env, capture_output=True, text=True, check=True)
    return json.loads(completed.stdout)


@pytest.mark.ac("AC-27")
@pytest.mark.ac("AC-24")
def test_separate_processes_resume_original_checkpoint_without_duplicate_events(tmp_path):
    paused = cli(tmp_path, "demo-start")
    assert paused["status"] == "PAUSED_FOR_HUMAN"
    assert paused["checkpoint_next"] == ["clarify"]
    replay = cli(tmp_path, "demo-start")
    assert replay["event_count"] == paused["event_count"]
    resumed = cli(tmp_path, "demo-answer", "--answer", "empty input should return 400")
    assert resumed["run_id"] == paused["run_id"] == resumed["thread_id"]
    assert resumed["status"] == "RUNNING"
    assert resumed["checkpoint_next"] == []
    assert resumed["questions"][0]["answer"] == "empty input should return 400"
    replay = cli(tmp_path, "demo-answer", "--answer", "empty input should return 400")
    assert replay["event_count"] == resumed["event_count"]
    with SQLiteStore(tmp_path / "state.db") as store:
        assert store.count_events_of_type(EventType.CLARIFICATION_REQUESTED) == 1
        assert store.count_events_of_type(EventType.CLARIFICATION_ANSWERED) == 1


@pytest.mark.ac("AC-51")
def test_state_and_event_both_roll_back_on_event_write_failure(tmp_path, monkeypatch):
    with SQLiteStore(tmp_path / "state.db") as store:
        service = StateTransitionService(store)
        run = service.create_run(run_id="r", run_type=RunType.DELIVERY, project_id="p",
            trigger_source="USER", config_snapshot_id="s")
        events = store.all_events()
        def fail(**kwargs):
            raise OSError("simulated disk failure")
        monkeypatch.setattr(store, "append_event", fail)
        with pytest.raises(OSError):
            service.transition("r", target_status=RunStatus.RUNNING, expected_version=run.state_version)
        assert store.get_run("r") == run
        assert store.all_events() == events
    with SQLiteStore(tmp_path / "state.db") as reopened:
        assert reopened.get_run("r") == run
        assert reopened.all_events() == events


@pytest.mark.ac("AC-51")
def test_two_sqlite_connections_do_not_overwrite_stale_state_version(tmp_path):
    with SQLiteStore(tmp_path / "state.db") as first, SQLiteStore(tmp_path / "state.db") as second:
        a, b = StateTransitionService(first), StateTransitionService(second)
        run = a.create_run(run_id="r", run_type=RunType.DELIVERY, project_id="p",
            trigger_source="USER", config_snapshot_id="s")
        a.transition("r", target_status=RunStatus.RUNNING, expected_version=run.state_version)
        before = first.all_events()
        with pytest.raises(TransitionRejected):
            b.transition("r", target_phase=RunPhase.PRODUCT, expected_version=run.state_version)
        assert second.get_run("r").phase is RunPhase.INTAKE
        assert second.all_events() == before


@pytest.mark.ac("AC-27")
def test_multiple_questions_restore_original_wait_state_only_after_all_answers(tmp_path):
    from datetime import timedelta
    from agentloop.core.contracts.models import utc_now
    from agentloop.core.orchestration.clarifications import ClarificationService
    with SQLiteStore(tmp_path / "state.db") as store:
        transitions, rbac = StateTransitionService(store), RBACService(store)
        rbac.register_principal("owner", PrincipalType.HUMAN_USER, "test://owner")
        rbac.bind_role(principal_id="owner", role_id="project_owner", scope_type="project", scope_id="p",
            valid_from=utc_now() - timedelta(seconds=1))
        transitions.create_run(run_id="r", run_type=RunType.DELIVERY, project_id="p",
            trigger_source="USER", config_snapshot_id="s")
        transitions.transition("r", target_status=RunStatus.RUNNING)
        transitions.transition("r", target_status=RunStatus.WAITING_APPROVAL)
        service = ClarificationService(store, transitions, rbac)
        questions = [service.ensure(run_id="r", question=text, kind=ClarificationKind.BUSINESS_DECISION)
                     for text in ("Which environment?", "Which target?")]
        service.answer(question_id=questions[0].question_id, principal_id="owner", answer="staging",
                       expected_version=store.get_run("r").state_version)
        assert store.get_run("r").status is RunStatus.PAUSED_FOR_HUMAN
        service.answer(question_id=questions[1].question_id, principal_id="owner", answer="server-1",
                       expected_version=store.get_run("r").state_version)
        assert store.get_run("r").status is RunStatus.WAITING_APPROVAL


@pytest.mark.ac("AC-48")
@pytest.mark.parametrize("actor", ["outsider", "agent"])
def test_other_project_and_agent_cannot_answer_clarification(tmp_path, actor):
    cli(tmp_path, "demo-start")
    from datetime import timedelta
    from agentloop.core.contracts.models import utc_now
    from agentloop.core.orchestration.clarifications import ClarificationService
    with SQLiteStore(tmp_path / "state.db") as store:
        rbac = RBACService(store)
        rbac.register_principal(actor, PrincipalType.AGENT_SERVICE if actor == "agent" else PrincipalType.HUMAN_USER,
                                "test://identity")
        rbac.bind_role(principal_id=actor, role_id="project_owner", scope_type="project", scope_id="other",
                        valid_from=utc_now() - timedelta(days=1))
        service = ClarificationService(store, StateTransitionService(store), rbac)
        question = store.clarifications_for("demo-run")[0]
        before = store.all_events()
        with pytest.raises(Exception):
            service.answer(question_id=question.question_id, principal_id=actor, answer="spoofed",
                           expected_version=store.get_run("demo-run").state_version)
        assert store.get_clarification(question.question_id).status is ClarificationStatus.OPEN
        assert store.get_run("demo-run").status is RunStatus.PAUSED_FOR_HUMAN
        assert store.all_events() == before
