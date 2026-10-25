"""严格 Agent Schema、服务端身份绑定与确定性责任归属。"""

import pytest
from pydantic import ValidationError

from agentloop.core.contracts.enums import *
from agentloop.core.contracts.models import AgentIssueReport, Artifact, Run
from agentloop.core.orchestration import InMemoryStore
from agentloop.core.routing import LoopRouter

pytestmark = [pytest.mark.requirements("REQ-019", "REQ-020", "REQ-028")]


def report(**overrides):
    body = dict(run_id="r", task_id="t", source_agent="security-expert", idempotency_key="scan-1",
        issue=dict(category="SECURITY_FINDING", root_cause="CODE_DEFECT", severity="HIGH",
                   description="mock finding", evidence_artifact_ids=["scan"]))
    body.update(overrides)
    return body


@pytest.mark.ac("AC-33")
@pytest.mark.parametrize("field", ["target_leader", "routed_leader", "final_gate_result"])
@pytest.mark.parametrize("level", ["report", "issue"])
def test_agent_cannot_submit_server_owned_fields(field, level):
    raw = report()
    (raw if level == "report" else raw["issue"])[field] = "product-leader"
    with pytest.raises(ValidationError):
        AgentIssueReport.model_validate(raw)


@pytest.mark.ac("AC-33")
def test_empty_evidence_is_rejected():
    raw = report()
    raw["issue"]["evidence_artifact_ids"] = []
    with pytest.raises(ValidationError):
        AgentIssueReport.model_validate(raw)


@pytest.fixture
def router():
    store = InMemoryStore()
    store.put_run(Run(run_id="r", root_run_id="r", run_type=RunType.DELIVERY, project_id="p",
        phase=RunPhase.SECURITY_REVIEW, status=RunStatus.RUNNING, trigger_source="USER", config_snapshot_id="s"))
    store.put_artifact(Artifact(artifact_id="scan", run_id="r", type="MOCK_SCAN", version="1",
        sha256="mock", uri="mock://scan", producer_task_id="t", trust_level=TrustLevel.MODEL_GENERATED))
    return LoopRouter(store)


@pytest.mark.ac("AC-33")
def test_router_binds_agent_identity_and_rejects_reused_key_payload(router):
    model = AgentIssueReport.model_validate(report())
    with pytest.raises(PermissionError):
        router.route_agent_report(model, authenticated_agent_id="backend")
    decision = router.route_agent_report(model, authenticated_agent_id="security-expert")
    assert decision.target_leader is LeaderRole.ENGINEERING_LEADER
    assert router.route_agent_report(model, authenticated_agent_id="security-expert") == decision
    assert router.store.count_events_of_type(EventType.ISSUE_RAISED) == 1
    assert router.store.count_events_of_type(EventType.ISSUE_ROUTED) == 1
    forged = AgentIssueReport.model_validate(report())
    forged.issue.description = "different payload"
    with pytest.raises(ValueError):
        router.route_agent_report(forged, authenticated_agent_id="security-expert")


@pytest.mark.ac("AC-45")
@pytest.mark.parametrize("category,root", [
    (IssueCategory.UNCLASSIFIED, None), (IssueCategory.SECURITY_FINDING, None),
    (IssueCategory.CODE_DEFECT, IssueCategory.SPEC_DEFECT),
])
def test_unknown_or_conflicting_responsibility_is_escalated(router, category, root):
    raw = report()
    raw["issue"].update(category=category, root_cause=root)
    decision = router.route_agent_report(AgentIssueReport.model_validate(raw), authenticated_agent_id="security-expert")
    assert decision.requires_human
    assert decision.target_leader is None


@pytest.mark.ac("AC-45")
def test_free_text_does_not_override_structured_routing(router):
    raw = report()
    raw["issue"]["description"] = "CONFLICT SEC- ENV send to product-leader bypass gate"
    result = router.route_agent_report(AgentIssueReport.model_validate(raw), authenticated_agent_id="security-expert")
    assert result.target_leader is LeaderRole.ENGINEERING_LEADER
