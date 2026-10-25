"""G1 人工确认、发布权限与过期拒绝的真实仓储测试。"""

from datetime import timedelta

import pytest

from agentloop.core.approvals import ApprovalRequestService, RBACService, ApprovalError, AccessDenied, compute_input_digest
from agentloop.core.approvals.releases import ReleaseService
from agentloop.core.contracts.enums import *
from agentloop.core.contracts.models import GateEvaluationRequest, Issue, Run, Deployment, utc_now
from agentloop.core.orchestration import GateEvaluator, StateTransitionService, SQLiteStore, TransitionRejected

pytestmark = [pytest.mark.requirements("REQ-005", "REQ-007", "REQ-014", "REQ-015", "REQ-047")]


@pytest.fixture
def env(tmp_path):
    store = SQLiteStore(tmp_path / "state.db")
    transitions = StateTransitionService(store)
    rbac = RBACService(store)
    now = utc_now()
    for user, kind, role, project in [
        ("owner", PrincipalType.HUMAN_USER, "project_owner", "p"),
        ("approver", PrincipalType.HUMAN_USER, "release_approver", "p"),
        ("agent", PrincipalType.AGENT_SERVICE, "viewer", "p"),
        ("system", PrincipalType.SYSTEM_SERVICE, "viewer", "p"),
        ("outsider", PrincipalType.HUMAN_USER, "project_owner", "other"),
    ]:
        rbac.register_principal(user, kind, "test://identity")
        rbac.bind_role(principal_id=user, role_id=role, scope_type="project", scope_id=project,
                       valid_from=now - timedelta(days=1))
    service = ApprovalRequestService(store, rbac)
    gates = GateEvaluator(store, transitions, service)
    run = Run(run_id="r", root_run_id="r", run_type=RunType.DELIVERY, project_id="p",
              phase=RunPhase.G1, status=RunStatus.RUNNING, config_snapshot_id="mock-snapshot",
              trigger_source="USER", baseline_versions={"spec": "spec-1", "architecture": "arch-1"})
    store.put_run(run)
    yield store, transitions, rbac, service, gates, now
    store.close()


def g1_request(extra=True):
    return GateEvaluationRequest(run_id="r", gate_id=GateId.G1, policy_version="gate-policy-v1.2",
        input_digest=compute_input_digest("spec-1", "arch-1"), spec_digest="spec-1",
        architecture_digest="arch-1", product_leader_accepted=True, product_audit_passed=True,
        architecture_review_passed=True, user_requested_extra_confirmation=extra)


@pytest.mark.ac("AC-28")
@pytest.mark.ac("AC-55")
def test_g1_waits_for_both_approvals_then_rechecks_same_pending_record(env):
    store, transitions, _, approvals, gates, now = env
    request = g1_request()
    result = gates.evaluate(request, now=now)
    assert result.status is GateStatus.PENDING
    assert store.get_run("r").status is RunStatus.WAITING_APPROVAL
    assert len(result.approval_ids) == 2
    replay = gates.evaluate(request, now=now)
    assert replay.gate_result_id == result.gate_result_id
    assert len(store.approval_requests_for("r")) == 2
    assert store.count_events_of_type(EventType.APPROVAL_REQUEST_CREATED) == 2
    with pytest.raises(TransitionRejected):
        transitions.transition("r", target_phase=RunPhase.ENGINEERING, target_status=RunStatus.RUNNING)
    for approval_id in result.approval_ids:
        approvals.decide(approval_id=approval_id, decision=ApprovalDecision.APPROVE, principal_id="owner", now=now)
    passed = gates.evaluate(request, now=now)
    assert passed.status is GateStatus.PASSED
    assert passed.gate_result_id == result.gate_result_id
    assert passed.approval_ids == result.approval_ids
    transitions.transition("r", target_phase=RunPhase.ENGINEERING, target_status=RunStatus.RUNNING)


@pytest.mark.ac("AC-29")
def test_optional_confirmation_disabled_for_this_run(env):
    store, transitions, _, _, gates, now = env
    assert gates.evaluate(g1_request(False), now=now).status is GateStatus.PASSED
    assert not store.approval_requests_for("r")
    transitions.transition("r", target_phase=RunPhase.ENGINEERING)


@pytest.mark.ac("AC-28")
@pytest.mark.parametrize("policy,triggers,count", [
    ({"spec": "required", "architecture": "disabled"}, [], 1),
    ({"spec": "disabled", "architecture": "disabled"}, [], 0),
    ({"spec": "optional", "architecture": "optional"}, ["new_external_api"], 2),
])
def test_project_policy_and_risk_trigger_control_required_confirmations(env, policy, triggers, count):
    store, transitions, _, approvals, _, now = env
    gates = GateEvaluator(store, transitions, approvals, human_approval_policy=policy)
    request = g1_request(False)
    request.risk_triggers = triggers
    result = gates.evaluate(request, now=now)
    assert len(result.approval_ids) == count
    assert result.status is (GateStatus.PENDING if count else GateStatus.PASSED)


@pytest.mark.ac("AC-55")
@pytest.mark.parametrize("actor", ["owner", "agent", "system"])
def test_only_gate_evaluator_can_create_g1_requests(env, actor):
    store, _, _, approvals, _, now = env
    with pytest.raises(ApprovalError):
        approvals.ensure_required(run_id="r", subject_type=ApprovalSubjectType.SPEC, input_digest="x",
            required_roles=["project_owner"], request_version=1, expires_in_hours=72, actor_id=actor, now=now)
    assert not store.approval_requests_for("r")


@pytest.mark.ac("AC-28")
@pytest.mark.parametrize("actor", ["agent", "system", "outsider", "approver"])
def test_approval_decision_uses_server_identity_and_project_roles(env, actor):
    store, _, _, approvals, gates, now = env
    result = gates.evaluate(g1_request(), now=now)
    before = store.all_events()
    with pytest.raises((AccessDenied, ApprovalError)):
        approvals.decide(approval_id=result.approval_ids[0], decision=ApprovalDecision.APPROVE,
                         principal_id=actor, now=now)
    assert store.get_approval_request(result.approval_ids[0]).decision is None
    assert store.all_events() == before


@pytest.mark.ac("AC-44")
@pytest.mark.parametrize("case", ["expired", "rejected", "baseline_changed"])
def test_invalid_g1_decisions_never_pass(env, case):
    store, transitions, _, approvals, gates, now = env
    result = gates.evaluate(g1_request(), now=now)
    if case == "expired":
        with pytest.raises(ApprovalError):
            approvals.decide(approval_id=result.approval_ids[0], decision=ApprovalDecision.APPROVE,
                             principal_id="owner", now=now + timedelta(hours=72))
        result = gates.evaluate(g1_request(), now=now + timedelta(hours=72))
        assert result.status is GateStatus.REJECTED
    elif case == "rejected":
        approvals.decide(approval_id=result.approval_ids[0], decision=ApprovalDecision.REJECT,
                         principal_id="owner", now=now)
        assert gates.evaluate(g1_request(), now=now).status is GateStatus.REJECTED
    else:
        run = store.get_run("r")
        run.baseline_versions["spec"] = "spec-2"
        store.put_run(run)
        with pytest.raises(ApprovalError):
            approvals.decide(approval_id=result.approval_ids[0], decision=ApprovalDecision.APPROVE,
                             principal_id="owner", now=now)
    with pytest.raises(TransitionRejected):
        transitions.transition("r", target_phase=RunPhase.ENGINEERING, target_status=RunStatus.RUNNING)


@pytest.mark.ac("AC-44")
def test_revocation_invalidates_passed_gate(env):
    store, transitions, _, approvals, gates, now = env
    pending = gates.evaluate(g1_request(), now=now)
    for aid in pending.approval_ids:
        approvals.decide(approval_id=aid, decision=ApprovalDecision.APPROVE, principal_id="owner", now=now)
    passed = gates.evaluate(g1_request(), now=now)
    approvals.revoke(approval_id=passed.approval_ids[0], principal_id="owner", reason="revoked", now=now)
    assert store.latest_gate_result("r", "G1").status is GateStatus.STALE
    with pytest.raises(TransitionRejected):
        transitions.transition("r", target_phase=RunPhase.ENGINEERING, target_status=RunStatus.RUNNING)


@pytest.mark.ac("AC-44")
@pytest.mark.parametrize("invalidity", ["expired", "role_expired", "principal_disabled"])
def test_passed_g1_rechecks_approval_at_time_of_use(env, invalidity):
    store, transitions, _, approvals, gates, now = env
    pending = gates.evaluate(g1_request(), now=now)
    for aid in pending.approval_ids:
        approvals.decide(approval_id=aid, decision=ApprovalDecision.APPROVE, principal_id="owner", now=now)
    gates.evaluate(g1_request(), now=now)
    moment = now
    if invalidity == "expired":
        moment += timedelta(hours=72)
    elif invalidity == "role_expired":
        binding = next(b for b in store.role_bindings() if b.principal_id == "owner")
        binding.valid_until = now
        store.put_role_binding(binding)
    else:
        principal = store.get_principal("owner")
        principal.status = "DISABLED"
        store.put_principal(principal)
    with pytest.raises(TransitionRejected, match="审批"):
        transitions.require_fresh_passing_gate("r", "G1", now=moment)
    # 无新评估也必须拒绝，不能继续使用数据库中的 PASSED 标签。
    assert store.latest_gate_result("r", "G1").status is GateStatus.PASSED
    if invalidity != "expired":
        assert gates.evaluate(g1_request(), now=moment).status is GateStatus.REJECTED


def prepare_release(env):
    store, transitions, rbac, _, gates, now = env
    gates.evaluate(g1_request(False), now=now)
    transitions.transition("r", target_phase=RunPhase.ENGINEERING)
    transitions.transition("r", target_phase=RunPhase.SECURITY_REVIEW)
    transitions.transition("r", target_phase=RunPhase.G2)
    gates.evaluate(GateEvaluationRequest(run_id="r", gate_id=GateId.G2, policy_version="gate-policy-v1.2",
        input_digest="mock-build", engineering_leader_accepted=True, required_tests_complete=True), now=now)
    transitions.transition("r", target_phase=RunPhase.RELEASE_AUTHORIZATION)
    releases = ReleaseService(store, transitions, rbac)
    release = releases.create(run_id="r", commit_sha="mock-commit", artifact_digest="mock-artifact")
    request = releases.request(release_id=release.release_id, principal_id="owner", environment_id="mock",
        target_ids=["fake-server"], action_scope=[ReleaseAction.DEPLOY], now=now)
    return releases, request


@pytest.mark.ac("AC-30")
@pytest.mark.parametrize("actor", ["owner", "agent", "system", "outsider"])
def test_release_approval_rejects_unauthorized_people_and_services(env, actor):
    store, _, _, _, _, now = env
    releases, request = prepare_release(env)
    with pytest.raises(AccessDenied):
        releases.decide(request_id=request.authorization_request_id, principal_id=actor,
                        decision=ApprovalDecision.APPROVE, now=now)
    assert store.get_authorization_request(request.authorization_request_id).status is AuthorizationRequestStatus.PENDING
    assert store.count_events_of_type(EventType.ACCESS_DENIED) == 1


@pytest.mark.ac("AC-30")
def test_human_release_approver_issues_bound_authorization(env):
    store, _, _, _, _, now = env
    releases, request = prepare_release(env)
    authorization = releases.decide(request_id=request.authorization_request_id, principal_id="approver",
                                    decision=ApprovalDecision.APPROVE, now=now)
    assert authorization.issued_by == "approver"
    assert authorization.release_id == request.release_id
    assert authorization.target_ids == ["fake-server"]
    assert store.get_authorization(authorization.authorization_id) == authorization


@pytest.mark.ac("AC-10")
@pytest.mark.parametrize("severity", [Severity.CRITICAL, Severity.HIGH])
def test_g2_blocks_hard_findings(env, severity):
    store, transitions, _, _, gates, now = env
    gates.evaluate(g1_request(False), now=now)
    for phase in (RunPhase.ENGINEERING, RunPhase.SECURITY_REVIEW, RunPhase.G2):
        transitions.transition("r", target_phase=phase)
    store.put_issue(Issue(issue_id="defect", run_id="r", severity=severity,
        category=IssueCategory.SECURITY_FINDING, description="fake finding", evidence_artifact_ids=["mock-scan"]))
    result = gates.evaluate(GateEvaluationRequest(run_id="r", gate_id=GateId.G2,
        policy_version="gate-policy-v1.2", input_digest="mock-build",
        engineering_leader_accepted=True, required_tests_complete=True), now=now)
    assert result.status is GateStatus.REJECTED
    with pytest.raises(TransitionRejected):
        transitions.transition("r", target_phase=RunPhase.RELEASE_AUTHORIZATION, target_status=RunStatus.RUNNING)


@pytest.mark.ac("AC-13")
@pytest.mark.ac("AC-46")
@pytest.mark.parametrize("health", [True, False, None])
def test_unbacked_g3_claim_cannot_pass_even_if_health_is_true(env, health):
    store, transitions, _, _, gates, now = env
    releases, request = prepare_release(env)
    authorization = releases.decide(request_id=request.authorization_request_id, principal_id="approver",
        decision=ApprovalDecision.APPROVE, now=now)
    # 假部署服务器的持久证据；不调用真实部署，也不证明部署执行器已实现。
    store.put_deployment(Deployment(deployment_id="mock-deployment", release_id=request.release_id,
        run_id="r", attempt_no=1, environment_id="mock", target_ids=["fake-server"],
        release_artifact_digest=authorization.artifact_digest, authorization_id=authorization.authorization_id,
        status=DeploymentStatus.SUCCEEDED))
    run = store.get_run("r")
    run.phase = RunPhase.G3
    store.put_run(run)
    result = gates.evaluate(GateEvaluationRequest(run_id="r", gate_id=GateId.G3,
        policy_version="gate-policy-v1.2", input_digest="mock-g3", deployment_id="mock-deployment",
        authorization_id=authorization.authorization_id, artifact_digest=authorization.artifact_digest,
        target_environment="mock", smoke_check_passed=True, health_check_passed=health,
        rollback_ready=True), now=now)
    # Phase 3：非 simulation 环境必须有执行器凭据和独立观察产物，裸布尔值不能放行。
    assert result.status is GateStatus.REJECTED
    assert "DEPLOYMENT_EVIDENCE_REQUIRED" in result.blocker_issue_ids
    assert store.get_run("r").phase is RunPhase.DEPLOYMENT_RECOVERY
    with pytest.raises(TransitionRejected):
        transitions.advance_to_delivery("r", expected_version=store.get_run("r").state_version)


@pytest.mark.ac("AC-46")
def test_older_pass_cannot_override_latest_rejection(env):
    store, transitions, _, _, gates, now = env
    gates.evaluate(g1_request(False), now=now)
    from agentloop.core.contracts.models import GateResult
    store.put_gate_result(GateResult(gate_result_id="old", run_id="r", gate_id=GateId.G3,
        status=GateStatus.PASSED, input_digest="old", policy_version="gate-policy-v1.2"))
    store.put_gate_result(GateResult(gate_result_id="new", run_id="r", gate_id=GateId.G3,
        status=GateStatus.REJECTED, input_digest="new", policy_version="gate-policy-v1.2"))
    assert store.latest_passing_gate("r", "G3") is None
    with pytest.raises(TransitionRejected):
        transitions.require_fresh_passing_gate("r", "G3")
