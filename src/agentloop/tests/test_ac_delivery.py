"""Phase 1 编排验收。快速用例注入明确标注的假测试执行器。"""

from collections import Counter
import json

import pytest

from agentloop.core.contracts.enums import EventType, GateStatus, RunStatus
from agentloop.examples.demo import build_demo
from agentloop.examples.scripted import ScriptedDemoAdapter

pytestmark = [pytest.mark.requirements("REQ-003", "REQ-005", "REQ-008", "REQ-009", "REQ-010", "REQ-011", "REQ-021", "REQ-032")]


class FakeTestRunner:
    """只用于编排单元测试，真实 Maven 验收由 java_integration 单独执行。"""
    def __init__(self, always_fail=False):
        self.calls = 0
        self.always_fail = always_fail

    def run(self, workspace, *, attempt):
        self.calls += 1
        code = (workspace.root / "src/main/java/example/HelloController.java").read_text(encoding="utf-8")
        passed = not self.always_fail and "name.isBlank()" in code
        return {"decision": "PASS" if passed else "FAIL", "commit_sha": workspace.commit(), "total": 4,
                "failed": 0 if passed else 2, "skipped": 0, "required_tests_complete": True,
                "integrity_valid": True, "log": "FAKE_TEST_EXECUTOR: unit test only"}


class SpyAdapter(ScriptedDemoAdapter):
    def __init__(self, reject_review=False, reject_audit_once=False, security_high=False):
        self.calls = []
        self.reject_review, self.reject_audit_once, self.security_high = reject_review, reject_audit_once, security_high

    def invoke(self, role, context, schema):
        self.calls.append((role, context))
        output = super().invoke(role, context, schema)
        if role == "product-analyst" and self.reject_audit_once and context["attempt"] > 1:
            output["goal"] += "；明确保留合法参数的历史行为"
        if role == "code-review" and self.reject_review and context["attempt"] == 1:
            output["accepted"] = False
            output["reasons"] = ["retry the implementation"]
        if role == "product-expert" and self.reject_audit_once and context["attempt"] == 1:
            output["accepted"] = False
            output["reasons"] = ["spec needs refinement"]
        if role == "security-expert" and self.security_high:
            output["findings"] = [{"severity": "HIGH" if self.security_high is True else self.security_high,
                                   "description": "injected candidate finding"}]
        return output


@pytest.fixture
def factory(tmp_path):
    opened = []
    def create(**kwargs):
        workflow = build_demo(data_dir=tmp_path, run_id="r", runner=kwargs.pop("runner", FakeTestRunner()), **kwargs)
        opened.append(workflow)
        return workflow
    yield create
    for workflow in opened:
        workflow.close()
        workflow.store.close()


@pytest.mark.ac("AC-06")
@pytest.mark.ac("AC-01")
def test_local_rework_skips_leader_and_waits_for_explicit_simulation_authorization(factory):
    adapter = SpyAdapter()
    workflow = factory(adapter=adapter)
    pending = workflow.start("r", "fix bug")
    assert pending["phase"] == "RELEASE_AUTHORIZATION"
    assert pending["status"] == "WAITING_APPROVAL"
    assert workflow.runner.calls == 2
    roles = Counter(role for role, _ in adapter.calls)
    assert roles["backend"] == 2
    assert roles["testing"] == 1
    assert roles["engineering-leader"] == 2  # 一次入口，一次最终出口。
    assert roles["product-leader"] == 1
    assert not workflow.store.deployments_for("r")
    assert workflow.store.count_events_of_type(EventType.LOCAL_REWORK) == 1
    delivered = workflow.authorize_simulation("r", "demo-owner")
    assert (delivered["phase"], delivered["status"]) == ("DELIVERY", "COMPLETED")
    assert workflow.store.deployments_for("r")[0].environment_id == "simulation"
    assert all(workflow.store.latest_gate_result("r", gate).status is GateStatus.PASSED for gate in ("G1", "G2", "G3"))


@pytest.mark.ac("AC-28")
def test_g1_checkpoint_blocks_all_backend_calls_until_human_confirmation(factory):
    adapter = SpyAdapter()
    workflow = factory(adapter=adapter, require_confirmation=True)
    paused = workflow.start("r", "fix bug")
    assert paused["phase"] == "G1"
    assert paused["status"] == "WAITING_APPROVAL"
    assert "backend" not in [role for role, _ in adapter.calls]
    assert workflow.runner.calls == 0
    resumed = workflow.confirm_g1("r", "demo-owner")
    assert resumed["phase"] == "RELEASE_AUTHORIZATION"
    assert workflow.runner.calls == 2
    assert len(workflow.store.approval_requests_for("r")) == 2


@pytest.mark.ac("AC-03")
def test_product_audit_rejection_routes_to_product_leader(factory):
    workflow = factory(adapter=SpyAdapter(reject_audit_once=True))
    result = workflow.start("r", "fix bug")
    assert result["phase"] == "RELEASE_AUTHORIZATION"
    issue = workflow.store.list_issues("r")[0]
    assert issue.routed_leader.value == "product-leader"
    assert workflow.store.count_events_of_type(EventType.DEPARTMENT_ACCEPTED) == 4


@pytest.mark.ac("AC-34")
@pytest.mark.parametrize("ui", [True, False])
def test_ux_and_production_review_triggers_are_recorded(factory, ui):
    adapter = SpyAdapter()
    workflow = factory(adapter=adapter)
    workflow.config.changes_ui = ui
    workflow.config.production_code_changed = False  # 实际源码 Diff 仍必须触发审查。
    workflow.start("r", "fix bug")
    roles = Counter(role for role, _ in adapter.calls)
    assert roles["ux-agent"] == int(ui)
    assert roles["code-review"] == 2
    triggered = [json.loads(e.payload_ref) for e in workflow.store.events_for("r") if e.type is EventType.CHECK_TRIGGERED]
    assert any(e["role"] == "ux-agent" and e["triggered"] == ui for e in triggered)


@pytest.mark.ac("AC-08")
def test_repeated_test_failure_is_bounded(factory):
    runner = FakeTestRunner(always_fail=True)
    workflow = factory(runner=runner)
    result = workflow.start("r", "fix bug")
    assert result["status"] == "BLOCKED"
    assert runner.calls == workflow.config.max_rework_rounds
    assert workflow.store.latest_gate_result("r", "G2") is None


@pytest.mark.ac("AC-09", "AC-34")
@pytest.mark.parametrize("target", ["ux-agent", "engineering-leader"])
def test_leader_and_ux_rejection_reenter_bounded_local_loop(factory, target):
    class RejectOnce(SpyAdapter):
        rejected = False
        def invoke(self, role, context, schema):
            output = super().invoke(role, context, schema)
            if role == target and not self.rejected and (target == "ux-agent" or context.get("mode") == "EXIT"):
                self.rejected = True
                output.update(accepted=False, reasons=["candidate requires refinement"])
            return output
    adapter = RejectOnce()
    workflow = factory(adapter=adapter)
    workflow.config.changes_ui = True
    assert workflow.start("r", "fix bug")["phase"] == "RELEASE_AUTHORIZATION"
    assert adapter.rejected
    assert sum(role == target for role, _ in adapter.calls) >= 2


@pytest.mark.ac("AC-10")
@pytest.mark.ac("AC-11")
@pytest.mark.parametrize("severity", ["HIGH", "CRITICAL"])
def test_high_security_finding_blocks_g2_even_after_passing_tests(factory, severity):
    workflow = factory(adapter=SpyAdapter(security_high=severity))
    result = workflow.start("r", "fix bug")
    assert result["phase"] == "G2"
    assert result["status"] == "BLOCKED"
    assert workflow.store.latest_gate_result("r", "G2").status is GateStatus.REJECTED
    assert not workflow.store.releases_for("r")


@pytest.mark.ac("AC-34")
def test_review_failure_returns_directly_to_backend(factory):
    workflow = factory(adapter=SpyAdapter(reject_review=True))
    result = workflow.start("r", "fix bug")
    assert result["phase"] == "RELEASE_AUTHORIZATION"
    assert workflow.runner.calls == 1  # 第一轮审查失败时不把测试结果当放行依据。


@pytest.mark.ac("AC-17")
def test_configuration_cannot_be_replaced_when_resuming(factory):
    workflow = factory()
    workflow.start("r", "fix bug")
    workflow.config.max_rework_rounds = 9
    with pytest.raises(ValueError, match="快照"):
        workflow.start("r", "fix bug")


def test_bound_commit_requires_original_delivery_evidence_in_g2(factory):
    from agentloop.core.contracts.enums import RunPhase, GateId
    from agentloop.core.contracts.models import GateEvaluationRequest
    workflow = factory()
    workflow.start("r", "fix bug")
    for phase in (RunPhase.ENGINEERING, RunPhase.SECURITY_REVIEW, RunPhase.G2):
        workflow.transitions.transition("r", target_phase=phase, target_status=RunStatus.RUNNING)
    result = workflow.gates.evaluate(GateEvaluationRequest(run_id="r", gate_id=GateId.G2,
        policy_version=workflow.gates.policy_version, input_digest="model-says-pass",
        engineering_leader_accepted=True, required_tests_complete=True))
    assert result.status is GateStatus.REJECTED
    assert "DELIVERY_EVIDENCE_REQUIRED" in result.blocker_issue_ids


@pytest.mark.ac("AC-24")
def test_reopen_g1_uses_original_configuration_and_cached_department_outputs(tmp_path):
    adapter = SpyAdapter()
    first = build_demo(data_dir=tmp_path, run_id="r", runner=FakeTestRunner(), adapter=adapter, require_confirmation=True)
    try:
        assert first.start("r", "fix bug")["phase"] == "G1"
        initial_calls = len(adapter.calls)
    finally:
        first.close()
        first.store.close()
    second = build_demo(data_dir=tmp_path, run_id="r", runner=FakeTestRunner(), adapter=adapter)
    try:
        assert second.config.require_confirmation is True
        assert second.start("r", "fix bug")["phase"] == "G1"
        assert len(adapter.calls) == initial_calls
        assert second.confirm_g1("r", "demo-owner")["phase"] == "RELEASE_AUTHORIZATION"
    finally:
        second.close()
        second.store.close()


@pytest.mark.ac("AC-24")
def test_patch_committed_before_crash_is_replayed_without_a_second_model_proposal(tmp_path, monkeypatch):
    adapter = SpyAdapter()
    first = build_demo(data_dir=tmp_path, run_id="r", runner=FakeTestRunner(), adapter=adapter)
    original = first.workspace.apply
    def crash(*args, **kwargs):
        original(*args, **kwargs)
        raise OSError("simulated process failure after Git commit")
    monkeypatch.setattr(first.workspace, "apply", crash)
    try:
        # 崩溃被收敛为 BLOCKED + 证据，而不是传播或留下僵尸 RUNNING
        result = first.start("r", "fix bug")
        assert result["status"] == "BLOCKED"
        assert Counter(role for role, _ in adapter.calls)["backend"] == 1
    finally:
        first.close()
        first.store.close()
    second = build_demo(data_dir=tmp_path, run_id="r", runner=FakeTestRunner(), adapter=adapter)
    try:
        run = second.store.get_run("r")
        second.transitions.transition("r", target_status=RunStatus.RUNNING, expected_version=run.state_version)
        assert second.start("r", "fix bug")["phase"] == "RELEASE_AUTHORIZATION"
        assert Counter(role for role, _ in adapter.calls)["backend"] == 2
        assert len(second.workspace.git("log", "--format=%H").splitlines()) == 3
    finally:
        second.close()
        second.store.close()


def test_second_review_includes_changes_retained_from_the_first_commit(factory):
    class RetainedChange(SpyAdapter):
        def invoke(self, role, context, schema):
            output = super().invoke(role, context, schema)
            if role == "backend" and context["attempt"] == 1:
                output["changes"][0]["content"] += "\n// retained first-round change\n"
            return output
    adapter = RetainedChange()
    workflow = factory(adapter=adapter)
    assert workflow.start("r", "fix bug")["phase"] == "RELEASE_AUTHORIZATION"
    reviews = [context for role, context in adapter.calls if role == "code-review"]
    assert len(reviews) == 2
    assert "+// retained first-round change" in reviews[1]["diff"]
    assert "+        if (name == null || name.isBlank())" in reviews[1]["diff"]


def test_recovery_rejects_cached_tests_after_clean_head_change(tmp_path, monkeypatch):
    first = build_demo(data_dir=tmp_path, run_id="r", runner=FakeTestRunner())
    event = first._event
    def crash(state, kind, actor, key, value):
        if kind is EventType.TEST_EXECUTED and value["decision"] == "PASS":
            raise OSError("crash after passing test artifact persisted")
        return event(state, kind, actor, key, value)
    monkeypatch.setattr(first, "_event", crash)
    try:
        result = first.start("r", "fix bug")
        assert result["status"] == "BLOCKED"
        first.workspace.git("commit", "--allow-empty", "-m", "external HEAD drift")
    finally:
        first.close()
        first.store.close()
    second = build_demo(data_dir=tmp_path, run_id="r", runner=FakeTestRunner())
    try:
        run = second.store.get_run("r")
        second.transitions.transition("r", target_status=RunStatus.RUNNING, expected_version=run.state_version)
        assert second.start("r", "fix bug")["status"] == "BLOCKED"
        assert second.runner.calls == 0
        assert second.store.latest_gate_result("r", "G2") is None
    finally:
        second.close()
        second.store.close()


@pytest.mark.parametrize("drift", ["commit", "untracked_source"])
def test_workspace_change_before_authorization_cannot_issue_or_consume_permission(factory, drift):
    workflow = factory()
    workflow.start("r", "fix bug")
    if drift == "commit":
        workflow.workspace.git("commit", "--allow-empty", "-m", "external HEAD drift")
    else:
        (workflow.workspace.root / "src/main/java/example/Unreviewed.java").write_text("class Unreviewed {}", encoding="utf-8")
    with pytest.raises(ValueError, match="Commit"):
        workflow.authorize_simulation("r", "demo-owner")
    assert not workflow.store.deployments_for("r")
    assert workflow.store.count_events_of_type(EventType.RELEASE_AUTHORIZATION_REQUESTED) == 0


def test_simulation_rejects_authorization_from_an_obsolete_g2(factory):
    from agentloop.core.contracts.enums import ApprovalDecision, ReleaseAction, RunPhase
    from agentloop.core.runtime.simulation import SimulatedDeployment
    workflow = factory()
    workflow.start("r", "fix bug")
    release = workflow.store.releases_for("r")[-1]
    request = workflow.releases.request(release_id=release.release_id, principal_id="demo-owner",
        environment_id="simulation", target_ids=["local-simulator"], action_scope=[ReleaseAction.DEPLOY])
    authorization = workflow.releases.decide(request_id=request.authorization_request_id,
        principal_id="demo-owner", decision=ApprovalDecision.APPROVE)
    state = dict(workflow.graph.get_state(workflow._config("r")).values)
    for phase in (RunPhase.ENGINEERING, RunPhase.SECURITY_REVIEW):
        workflow.transitions.transition("r", target_phase=phase, target_status=RunStatus.RUNNING)
    workflow._g2(state)
    assert workflow.store.latest_gate_result("r", "G2").gate_result_id != release.g2_gate_result_id
    with pytest.raises(ValueError, match="G2"):
        SimulatedDeployment(workflow.store, workflow.transitions, workflow.rbac).execute("r", authorization.authorization_id)
    assert workflow.store.get_authorization(authorization.authorization_id).uses == 0
    assert not workflow.store.deployments_for("r")


def test_release_cannot_claim_commit_other_than_the_passing_g2(factory):
    workflow = factory()
    workflow.start("r", "fix bug")
    with pytest.raises(ValueError, match="Commit"):
        workflow.releases.create(run_id="r", commit_sha="different-commit", artifact_digest="candidate")
    assert len(workflow.store.releases_for("r")) == 1


@pytest.mark.parametrize("severity", ["HIGH", "CRITICAL"])
def test_new_blocker_after_g2_prevents_release_authorization(factory, severity):
    from agentloop.core.contracts.models import Issue
    from agentloop.core.contracts.enums import IssueCategory, Severity
    from agentloop.core.orchestration import TransitionRejected
    workflow = factory()
    workflow.start("r", "fix bug")
    workflow.store.put_issue(Issue(issue_id="late-finding", run_id="r", severity=Severity(severity),
        category=IssueCategory.CODE_DEFECT, description="late blocker", evidence_artifact_ids=["scan"]))
    with pytest.raises(TransitionRejected, match="严重问题"):
        workflow.authorize_simulation("r", "demo-owner")
    assert workflow.store.count_events_of_type(EventType.RELEASE_AUTHORIZATION_REQUESTED) == 0
    assert not workflow.store.deployments_for("r")


@pytest.mark.parametrize("forge_scope", [False, True])
def test_backend_receives_leader_plan_and_must_obey_approved_architecture(factory, forge_scope):
    from agentloop.examples.demo import EDITABLE_PATH
    from agentloop.core.runtime.workspace import file_digest
    extra = "src/main/java/example/Application.java"
    class NarrowScope(SpyAdapter):
        def invoke(self, role, context, schema):
            output = super().invoke(role, context, schema)
            if role == "architecture-expert":
                output["editable_paths"] = [EDITABLE_PATH]
            if role == "engineering-leader" and context.get("mode") == "ENTRY":
                output["backend_task"] = "specific leader assignment"
            if role == "backend":
                assert set(context["sources"]) == {EDITABLE_PATH}
                assert context["plan"]["backend_task"] == "specific leader assignment"
                assert context["architecture"]["editable_paths"] == [EDITABLE_PATH]
                if forge_scope:
                    output["changes"].append({"path": extra,
                        "expected_sha256": file_digest(workflow.workspace.root / extra), "content": "unauthorized"})
            return output
    workflow = factory(adapter=NarrowScope())
    workflow.workspace.editable_paths = frozenset({EDITABLE_PATH, extra})
    original = workflow.workspace.commit()
    result = workflow.start("r", "fix bug")
    if forge_scope:
        assert result["status"] == "BLOCKED"
        assert workflow.workspace.commit() == original
        assert workflow.runner.calls == 0
    else:
        assert result["phase"] == "RELEASE_AUTHORIZATION"


@pytest.mark.parametrize("damage", ["missing_reference", "corrupt_blob"])
def test_invalid_delivery_evidence_rejects_g2_instead_of_crashing(factory, damage):
    from pathlib import Path
    from agentloop.core.contracts.enums import RunPhase, GateId
    from agentloop.core.contracts.models import GateEvaluationRequest
    workflow = factory()
    workflow.start("r", "fix bug")
    evidence = next(a for a in workflow.store.artifacts_for("r") if a.type == "DELIVERY_EVIDENCE")
    if damage == "missing_reference":
        body = workflow.archive.read(evidence.artifact_id, run_id="r")
        body["test_id"] = "nonexistent"
        evidence = workflow.archive.put(run_id="r", kind="DELIVERY_EVIDENCE", producer="orchestrator:g2", value=body)
    else:
        Path(evidence.uri).write_text("{}", encoding="utf-8")
    for phase in (RunPhase.ENGINEERING, RunPhase.SECURITY_REVIEW, RunPhase.G2):
        workflow.transitions.transition("r", target_phase=phase, target_status=RunStatus.RUNNING)
    result = workflow.gates.evaluate(GateEvaluationRequest(run_id="r", gate_id=GateId.G2,
        policy_version=workflow.gates.policy_version, input_digest=evidence.sha256,
        evidence_artifact_id=evidence.artifact_id, engineering_leader_accepted=True, required_tests_complete=True))
    assert result.status is GateStatus.REJECTED
    assert workflow.store.get_run("r").status is RunStatus.BLOCKED
    assert "DELIVERY_EVIDENCE_UNREADABLE_OR_INVALID" in result.blocker_issue_ids


@pytest.mark.ac("AC-06")
def test_unexpected_node_exception_blocks_run_with_evidence_and_stays_resumable(factory, monkeypatch):
    """未预期异常不得留下永久 RUNNING 的僵尸 Run：必须落 BLOCKED + 证据，且可恢复。"""
    workflow = factory()

    def crash(workspace, *, attempt):
        raise KeyError("workspace file vanished")

    monkeypatch.setattr(workflow.runner, "run", crash)
    result = workflow.start("r", "fix bug")
    assert result["status"] == "BLOCKED"
    blocked = [a for a in workflow.store.artifacts_for("r") if a.type == "WORKFLOW_BLOCKED"]
    assert blocked
    body = workflow.archive.read(blocked[-1].artifact_id, run_id="r")
    assert "unexpected KeyError" in body["reason"]

    monkeypatch.undo()
    run = workflow.store.get_run("r")
    workflow.transitions.transition("r", target_status=RunStatus.RUNNING, expected_version=run.state_version)
    resumed = workflow.start("r", "fix bug")
    assert resumed["phase"] == "RELEASE_AUTHORIZATION" and resumed["status"] == "WAITING_APPROVAL"
