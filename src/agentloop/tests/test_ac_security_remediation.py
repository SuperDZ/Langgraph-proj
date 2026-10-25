"""G2 责任验证、外部工单、整改结算和恢复。执行器为显式假实现。"""

from collections import Counter

import pytest

from agentloop.core.contracts.enums import EventType, GateStatus, IssueCategory, IssueStatus, RunStatus
from agentloop.examples.demo import build_demo
from agentloop.examples.scripted import ScriptedSecurityRepairAdapter
from .test_ac_delivery import FakeTestRunner, SpyAdapter

pytestmark = [pytest.mark.ac("AC-59"), pytest.mark.ac("AC-10"),
              pytest.mark.requirements("REQ-002", "REQ-012", "REQ-019", "REQ-020", "REQ-049")]


class RepairSpy(ScriptedSecurityRepairAdapter):
    def __init__(self, repair=True, noop=False):
        self.calls = []
        self.repair, self.noop = repair, noop

    def invoke(self, role, context, schema):
        self.calls.append((role, context))
        output = super().invoke(role, context, schema)
        if role == "backend" and context.get("remediation"):
            for change in output["changes"]:
                if self.noop:
                    change["content"] = context["sources"][change["path"]]
                elif not self.repair:
                    prefix, suffix = change["content"].rsplit("}", 1)
                    change["content"] = prefix + f"// ineffective round {context['attempt']}\n" + self.unsafe_method + "}" + suffix
        return output


def close(workflow):
    workflow.close()
    workflow.store.close()


def test_g2_verified_code_finding_reenters_leader_and_resolves_only_after_revalidation(tmp_path):
    adapter = RepairSpy()
    workflow = build_demo(data_dir=tmp_path, run_id="r", runner=FakeTestRunner(), adapter=adapter)
    protected = workflow.workspace.protected_digest()
    try:
        result = workflow.start("r", "fix and review")
        assert (result["phase"], result["status"]) == ("RELEASE_AUTHORIZATION", "WAITING_APPROVAL")
        assert [g.status for g in workflow.store.gate_results_for("r", "G2")] == [GateStatus.REJECTED, GateStatus.PASSED]
        assert len(workflow.store.gate_results_for("r", "G1")) == 1
        assert workflow.workspace.protected_digest() == protected
        issue = workflow.store.list_issues("r")[0]
        assert issue.category is IssueCategory.SECURITY_FINDING
        assert issue.root_cause is IssueCategory.CODE_DEFECT
        assert issue.routed_leader.value == "engineering-leader"
        assert issue.status is IssueStatus.RESOLVED
        resolution = next(a for a in workflow.store.artifacts_for("r") if a.type == "ISSUE_RESOLUTION")
        proof = workflow.archive.read(resolution.artifact_id, run_id="r")
        assert proof["commit"] == result["baseline"]["commit"]
        assert resolution.artifact_id in issue.evidence_artifact_ids
        assert Counter(role for role, _ in adapter.calls)["engineering-leader"] == 4
        entries = [c for role, c in adapter.calls if role == "engineering-leader" and c.get("mode") == "ENTRY"]
        assert len(entries) == 2 and entries[1]["remediation"]["issues"][0]["issue_id"] == issue.issue_id
        assert workflow.runner.calls == 3
        assert workflow.store.count_events_of_type(EventType.EXTERNAL_REWORK) == 1
        assert workflow.authorize_simulation("r", "demo-owner")["status"] == "COMPLETED"
    finally:
        close(workflow)


@pytest.mark.parametrize("noop", [False, True])
def test_unfixed_security_findings_stay_open_and_cannot_loop_forever(tmp_path, noop):
    workflow = build_demo(data_dir=tmp_path, run_id="r", runner=FakeTestRunner(), adapter=RepairSpy(repair=False, noop=noop))
    try:
        workflow.config.max_department_attempts = 2
        result = workflow.start("r", "fix and review")
        assert (result["phase"], result["status"]) == ("G2", "BLOCKED")
        assert not workflow.store.releases_for("r")
        assert all(i.status is not IssueStatus.RESOLVED for i in workflow.store.list_issues("r"))
        assert workflow.store.count_events_of_type(EventType.EXTERNAL_REWORK) == (1 if noop else 2)
        assert workflow.runner.calls <= 4
    finally:
        close(workflow)


def test_unknown_expert_root_cause_stays_unassigned_and_cannot_be_auto_resolved(tmp_path):
    workflow = build_demo(data_dir=tmp_path, run_id="r", runner=FakeTestRunner(), adapter=SpyAdapter(security_high=True))
    try:
        assert workflow.start("r", "fix")["status"] == "BLOCKED"
        issue = workflow.store.list_issues("r")[0]
        assert issue.category is IssueCategory.SECURITY_FINDING
        assert issue.root_cause is None and issue.routed_leader is None
        assert workflow.security_issues.repairable(issue) is False
        assert workflow.store.count_events_of_type(EventType.EXTERNAL_REWORK) == 0
    finally:
        close(workflow)


@pytest.mark.ac("AC-24")
@pytest.mark.parametrize("crash_event", [EventType.EXTERNAL_REWORK, EventType.ISSUE_RESOLVED])
def test_crash_after_remediation_commit_reuses_evidence_and_enters_leader_once(tmp_path, monkeypatch, crash_event):
    adapter = RepairSpy()
    first = build_demo(data_dir=tmp_path, run_id="r", runner=FakeTestRunner(), adapter=adapter)
    # 模拟业务事务已提交、图 checkpoint 尚未写入的间隙。
    from contextlib import contextmanager
    transaction = first.store.transaction
    @contextmanager
    def fail_after_commit():
        outer = first.store._depth == 0
        before = first.store.count_events_of_type(crash_event)
        with transaction():
            yield
        after = first.store.count_events_of_type(crash_event)
        if outer and before == 0 and after == 1:
            raise OSError("crash after atomic remediation order")
    monkeypatch.setattr(first.store, "transaction", fail_after_commit)
    try:
        # 崩溃被收敛为 BLOCKED + 证据；业务事务提交、checkpoint 未写入的现场保留
        result = first.start("r", "fix")
        assert result["status"] == "BLOCKED"
        assert first.store.count_events_of_type(crash_event) == 1
    finally:
        close(first)
    second = build_demo(data_dir=tmp_path, run_id="r", runner=FakeTestRunner(), adapter=adapter)
    try:
        run = second.store.get_run("r")
        second.transitions.transition("r", target_status=RunStatus.RUNNING, expected_version=run.state_version)
        assert second.start("r", "fix")["phase"] == "RELEASE_AUTHORIZATION"
        assert second.store.count_events_of_type(EventType.EXTERNAL_REWORK) == 1
        assert second.store.count_events_of_type(EventType.ISSUE_RESOLVED) == 1
        assert len([a for a in second.store.artifacts_for("r") if a.type == "REMEDIATION_ORDER"]) == 1
        entries = [c for role, c in adapter.calls if role == "engineering-leader" and c.get("mode") == "ENTRY"]
        assert len(entries) == 2
    finally:
        close(second)


@pytest.mark.parametrize("invalid_proof", ["failed_test", "stale_review"])
def test_issue_cannot_be_resolved_using_failed_or_old_delivery_proof(tmp_path, invalid_proof):
    workflow = build_demo(data_dir=tmp_path, run_id="r", runner=FakeTestRunner(), adapter=RepairSpy())
    try:
        workflow.start("r", "fix")
        issue = workflow.store.list_issues("r")[0]
        issue.status = IssueStatus.ROUTED
        issue.evidence_artifact_ids = issue.evidence_artifact_ids[:1]
        workflow.store.put_issue(issue)
        state = workflow.graph.get_state(workflow._config("r")).values
        test_id, review_id = state["test_id"], state["review_id"]
        if invalid_proof == "failed_test":
            test_id = next(a.artifact_id for a in workflow.store.artifacts_for("r") if a.type == "TEST_EXECUTION")
        else:
            review_id = next(a.artifact_id for a in workflow.store.artifacts_for("r")
                if a.type == "AGENT_REPLY" and workflow.archive.read(a.artifact_id, run_id="r")["role"] == "code-review")
        before = len(workflow.store.events_for("r"))
        with pytest.raises(ValueError):
            workflow.security_issues.record_scan("r", state["scan_id"], test_id=test_id,
                review_id=review_id, acceptance_id=state["acceptance_id"])
        assert workflow.store.get_issue(issue.issue_id).status is IssueStatus.ROUTED
        assert len(workflow.store.events_for("r")) == before
    finally:
        close(workflow)


def test_security_demo_profile_survives_reopen_without_repeating_the_flag(tmp_path):
    first = build_demo(data_dir=tmp_path, run_id="r", runner=FakeTestRunner(), security_example=True)
    try:
        assert first.start("r", "fix")["phase"] == "RELEASE_AUTHORIZATION"
    finally:
        close(first)
    second = build_demo(data_dir=tmp_path, run_id="r", runner=FakeTestRunner())
    try:
        assert second.config.role_profiles["backend"] == "scripted-security-demo"
        assert second.authorize_simulation("r", "demo-owner")["status"] == "COMPLETED"
    finally:
        close(second)
