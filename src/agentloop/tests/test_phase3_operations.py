"""Phase 3 发布、故障恢复、取消和子 Run 的独立故障注入。"""
from datetime import timedelta
import pytest
from agentloop.core.approvals import RBACService, compute_input_digest
from agentloop.core.approvals.releases import ReleaseService
from agentloop.core.contracts.enums import *
from agentloop.core.contracts.models import Run, GateResult, utc_now
from agentloop.core.contracts.phase3 import DeploymentTarget, ExecutionPolicy, DeploymentObservation
from agentloop.core.orchestration import InMemoryStore, SQLiteStore, StateTransitionService
from agentloop.core.runtime.configuration import RuntimeRepository
from agentloop.core.runtime.deployment_providers import LocalStaticProvider, bundle_digest
from agentloop.core.runtime.effects import SideEffectExecutor, EffectUncertain
from agentloop.core.runtime.operations import DeploymentCoordinator, CancellationService, MaintenanceService
from agentloop.knowledge.archive import ArtifactArchive

pytestmark = pytest.mark.requirements("REQ-014", "REQ-015", "REQ-016", "REQ-033", "REQ-034", "REQ-041", "REQ-044", "REQ-045", "REQ-049")


class Provider:
    """明确标记的外部服务模拟器；真实 HTTP 发布另有用例。"""
    def __init__(self):
        self.current = "baseline"; self.operations = {}; self.sent = []; self.unhealthy = False
        self.deploy_timeout = self.rollback_timeout = False
    def execute(self, operation_id, action, *, bundle, artifact_digest, previous_digest=None):
        self.sent.append(action)
        old = self.current
        self.current = artifact_digest if action == "DEPLOY" else previous_digest
        result = DeploymentObservation(operation_id=operation_id, status="SUCCEEDED", artifact_digest=self.current, previous_digest=old if action == "DEPLOY" else previous_digest)
        self.operations[operation_id] = result
        if (action == "DEPLOY" and self.deploy_timeout) or (action == "ROLLBACK" and self.rollback_timeout): raise TimeoutError()
        return result
    def query(self, operation_id): return self.operations.get(operation_id, DeploymentObservation(operation_id=operation_id, status="UNKNOWN"))
    def health(self, expected_digest):
        return {"artifact_digest": self.current, "healthy": self.current == expected_digest and (self.current == "baseline" or not self.unhealthy), "evidence": "FAULT INJECTION FIXTURE ONLY"}


@pytest.fixture(params=["memory", "sqlite"])
def ops(tmp_path, request):
    store = InMemoryStore() if request.param == "memory" else SQLiteStore(tmp_path / "state.db")
    moment = utc_now()
    clock = [moment]
    store.put_run(Run(run_id="r", root_run_id="r", run_type=RunType.DELIVERY, project_id="p",
        phase=RunPhase.RELEASE_AUTHORIZATION, status=RunStatus.WAITING_APPROVAL, trigger_source="TEST", config_snapshot_id="c",
        baseline_versions={"spec":"spec", "architecture":"arch", "commit":"commit"}))
    for gate in (GateId.G1, GateId.G2):
        store.put_gate_result(GateResult(gate_result_id=gate.value, run_id="r", gate_id=gate, status=GateStatus.PASSED,
            policy_version="gate-policy-v1.2", input_digest=compute_input_digest("spec", "arch") if gate is GateId.G1 else "g2",
            commit_sha="commit" if gate is GateId.G2 else None))
    rbac = RBACService(store)
    for who, kind in [("owner", PrincipalType.HUMAN_USER), ("ops", PrincipalType.AGENT_SERVICE), ("backend", PrincipalType.AGENT_SERVICE), ("executor", PrincipalType.SYSTEM_SERVICE)]:
        rbac.register_principal(who, kind, "test://" + who)
    for who, roles in {"owner":["project_owner","release_approver","operator","security_reviewer"], "ops":["viewer"], "backend":["viewer"], "executor":["side_effect_executor"]}.items():
        for role in roles: rbac.bind_role(principal_id=who, role_id=role, scope_type="project", scope_id="p", valid_from=moment-timedelta(seconds=1))
    repo = RuntimeRepository(store, ArtifactArchive(tmp_path / "artifacts", store))
    provider = Provider()
    executor = SideEffectExecutor(repo, service_principal="executor", providers={"t":provider}, clock=lambda:clock[0])
    target = DeploymentTarget(target_id="t", project_id="p", environment="staging", provider="local-static")
    executor.register_target(target, principal_id="owner")
    for who in ("ops", "backend"):
        executor.bind_policy("r", ExecutionPolicy(principal_id=who, role="operations-expert" if who=="ops" else "backend",
            platform=["cap.deploy.staging","cap.deploy.production"], department=["cap.deploy.staging","cap.deploy.production"],
            agent=["cap.deploy.staging","cap.deploy.production"], task=["cap.deploy.staging","cap.deploy.production"], target_ids=["t"]), principal_id="owner")
    bundle = {"files":{"index.html":"<!doctype html><title>AgentLoop</title>AgentLoop release"},"commit":"commit"}
    releases = ReleaseService(store, executor.transitions, rbac)
    release = releases.create(run_id="r", commit_sha="commit", artifact_digest=bundle_digest(bundle))
    request = releases.request(release_id=release.release_id, principal_id="owner", environment_id="staging", target_ids=["t"], action_scope=[ReleaseAction.DEPLOY, ReleaseAction.ROLLBACK], now=moment)
    authorization = releases.decide(request_id=request.authorization_request_id, principal_id="owner", decision=ApprovalDecision.APPROVE, now=moment)
    data = dict(store=store, repo=repo, provider=provider, executor=executor, coordinator=DeploymentCoordinator(executor),
        clock=clock, target=target, bundle=bundle, release=release, authorization=authorization, releases=releases)
    yield data
    if hasattr(store,"close"): store.close()


def deploy(ops, **overrides):
    args = dict(run_id="r", actor_id="ops", authorization_id=ops["authorization"].authorization_id, target_id="t", bundle=ops["bundle"], idempotency_key="first")
    return ops["executor"].execute(**{**args, **overrides})


@pytest.mark.ac("AC-12", "AC-54", "AC-56")
def test_independent_executor_requires_capability_and_exact_authorization(ops):
    with pytest.raises(PermissionError): deploy(ops, actor_id="backend")
    assert not ops["provider"].sent
    deployment = deploy(ops)
    assert deploy(ops).deployment_id == deployment.deployment_id
    assert ops["provider"].sent == ["DEPLOY"]
    result = ops["coordinator"].finalize(deployment.deployment_id, actor_id="ops")
    assert result.status is RunStatus.COMPLETED


@pytest.mark.ac("AC-31", "AC-54", "AC-56", "AC-57")
@pytest.mark.parametrize("failure", ["expired", "target", "artifact", "revoked", "approver"])
def test_invalid_authorizations_never_send_external_requests(ops, failure):
    auth = ops["authorization"]
    if failure == "expired": ops["clock"][0] += timedelta(hours=2)
    elif failure == "target":
        changed=ops["target"].model_copy(update={"expected_text":"changed"}); ops["executor"].register_target(changed, principal_id="owner")
    elif failure == "artifact":
        auth.artifact_digest="different"; ops["store"].put_authorization(auth)
    elif failure == "revoked": ops["releases"].revoke(auth.authorization_id,"owner")
    else:
        principal=ops["store"].get_principal("owner"); principal.status="DISABLED"; ops["store"].put_principal(principal)
    with pytest.raises(Exception): deploy(ops)
    assert not ops["provider"].sent
    assert not ops["store"].deployments_for("r")


@pytest.mark.ac("AC-49", "AC-58", "AC-59")
def test_g3_failure_safe_rollback_then_new_authorized_attempt(ops):
    ops["provider"].unhealthy=True
    deployment=deploy(ops)
    result=ops["coordinator"].finalize(deployment.deployment_id, actor_id="ops")
    assert (result.phase,result.status)==(RunPhase.DEPLOYMENT_RECOVERY,RunStatus.BLOCKED)
    assert ops["store"].latest_gate_result("r","G3").status is GateStatus.REJECTED
    assert ops["provider"].current=="baseline"
    ops["coordinator"].remediate(deployment.deployment_id,cause="ENV_DEFECT",principal_id="owner")
    request=ops["releases"].request(release_id=ops["release"].release_id,principal_id="owner",environment_id="staging",target_ids=["t"],action_scope=[ReleaseAction.DEPLOY,ReleaseAction.ROLLBACK],now=ops["clock"][0])
    auth=ops["releases"].decide(request_id=request.authorization_request_id,principal_id="owner",decision=ApprovalDecision.APPROVE,now=ops["clock"][0])
    ops["provider"].unhealthy=False
    second=deploy(ops,authorization_id=auth.authorization_id,idempotency_key="second")
    assert ops["coordinator"].finalize(second.deployment_id,actor_id="ops").status is RunStatus.COMPLETED
    assert [g.status for g in ops["store"].gate_results_for("r","G3")]==[GateStatus.REJECTED,GateStatus.PASSED]


@pytest.mark.ac("AC-50", "AC-24")
def test_unknown_rollback_requires_query_and_cannot_be_replayed(ops):
    ops["provider"].unhealthy=True; ops["provider"].rollback_timeout=True
    deployment=deploy(ops)
    result=ops["coordinator"].finalize(deployment.deployment_id,actor_id="ops")
    assert result.status is RunStatus.NEEDS_RECONCILIATION
    with pytest.raises(EffectUncertain): ops["executor"].rollback(deployment.deployment_id,actor_id="ops")
    effect=next(e for e in ops["store"].runtime_list("effect") if e["action"]=="ROLLBACK")
    ops["executor"].reconcile(effect["id"],principal_id="owner")
    result=ops["coordinator"].recover(deployment.deployment_id,actor_id="ops")
    assert result.status is RunStatus.BLOCKED
    assert ops["provider"].sent.count("ROLLBACK")==1


@pytest.mark.ac("AC-42")
def test_cancel_sent_deployment_reconciles_then_compensates(ops):
    ops["provider"].deploy_timeout=True
    with pytest.raises(EffectUncertain): deploy(ops)
    cancellation=CancellationService(ops["coordinator"])
    cancellation.request("r",principal_id="owner")
    result=cancellation.settle("r",principal_id="owner",actor_id="ops")
    assert result.status is RunStatus.CANCELLED
    assert ops["provider"].current=="baseline"
    assert ops["provider"].sent==["DEPLOY","ROLLBACK"]


@pytest.mark.ac("AC-42")
def test_cancel_unknown_operation_never_claims_no_effects(ops):
    ops["provider"].deploy_timeout=True
    with pytest.raises(EffectUncertain): deploy(ops)
    ops["provider"].operations.clear()
    cancellation=CancellationService(ops["coordinator"])
    cancellation.request("r",principal_id="owner")
    assert cancellation.settle("r",principal_id="owner",actor_id="ops").status is RunStatus.NEEDS_RECONCILIATION


@pytest.mark.ac("AC-59")
@pytest.mark.parametrize("cause,phase", [("CODE_DEFECT",RunPhase.ENGINEERING),("SPEC_DEFECT",RunPhase.PRODUCT),("ARCH_DEFECT",RunPhase.ARCHITECTURE)])
def test_safe_recovery_routes_upstream_and_invalidates_affected_gates(ops,cause,phase):
    ops["provider"].unhealthy=True
    deployment=deploy(ops); ops["coordinator"].finalize(deployment.deployment_id,actor_id="ops")
    result=ops["coordinator"].remediate(deployment.deployment_id,cause=cause,principal_id="owner")
    assert result.phase is phase
    assert ops["store"].latest_gate_result("r","G2").status is GateStatus.STALE
    assert ops["store"].latest_gate_result("r","G1").status is (GateStatus.PASSED if cause=="CODE_DEFECT" else GateStatus.STALE)


@pytest.mark.ac("AC-49", "AC-59")
def test_termination_requires_safe_rollback_evidence(ops):
    deployment=deploy(ops)
    with pytest.raises(ValueError): ops["coordinator"].terminate(deployment.deployment_id,principal_id="owner")
    ops["provider"].unhealthy=True; ops["coordinator"].finalize(deployment.deployment_id,actor_id="ops")
    assert ops["coordinator"].terminate(deployment.deployment_id,principal_id="owner").status is RunStatus.FAILED


@pytest.mark.ac("AC-26", "AC-35")
@pytest.mark.requirements("REQ-017", "REQ-038")
def test_periodic_maintenance_child_and_incident_leave_parent_unchanged(ops):
    deployment=deploy(ops); ops["coordinator"].finalize(deployment.deployment_id,actor_id="ops")
    parent=ops["store"].get_run("r")
    maintenance=MaintenanceService(ops["executor"])
    maintenance.schedule("r","t",principal_id="owner",interval_seconds=10)
    children=maintenance.tick()
    assert len(children)==1 and children[0].status is RunStatus.COMPLETED
    assert children[0].run_type is RunType.MAINTENANCE
    assert children[0].parent_run_id == parent.run_id
    assert children[0].root_run_id == parent.root_run_id
    assert maintenance.tick()==[]
    ops["clock"][0]+=timedelta(seconds=11); ops["provider"].unhealthy=True
    failed = maintenance.tick()[0]
    assert failed.status is RunStatus.BLOCKED
    incident = ops["store"].get_run("incident-" + failed.run_id)
    assert incident.run_type is RunType.INCIDENT
    assert incident.parent_run_id == failed.run_id
    assert incident.root_run_id == parent.root_run_id
    assert ops["store"].get_run("r")==parent


@pytest.mark.ac("AC-54")
def test_actual_local_http_deployment_and_provider_restart(ops,tmp_path):
    provider=LocalStaticProvider(tmp_path/"target",ops["target"])
    ops["executor"].providers["t"]=provider
    deployment=deploy(ops)
    assert provider.health(deployment.release_artifact_digest)["healthy"] is True
    provider.close()
    restarted=LocalStaticProvider(tmp_path/"target",ops["target"])
    ops["executor"].providers["t"]=restarted
    try:
        assert ops["coordinator"].finalize(deployment.deployment_id,actor_id="ops").status is RunStatus.COMPLETED
    finally: restarted.close()


@pytest.mark.ac("AC-42", "AC-50")
def test_recovery_cannot_be_cancelled_without_verified_safe_environment(ops):
    ops["provider"].unhealthy=True;ops["provider"].rollback_timeout=True
    deployment=deploy(ops);ops["coordinator"].finalize(deployment.deployment_id,actor_id="ops")
    service=CancellationService(ops["coordinator"]);service.request("r",principal_id="owner")
    run=ops["store"].get_run("r")
    from agentloop.core.orchestration import TransitionRejected
    with pytest.raises(TransitionRejected):
        ops["executor"].transitions.transition("r",target_status=RunStatus.CANCELLED,expected_version=run.state_version)


@pytest.mark.ac("AC-42")
def test_cancel_between_preparation_and_dispatch_sends_no_request(ops,monkeypatch):
    service=CancellationService(ops["coordinator"])
    original=ops["repo"].audit
    def cancel_at_boundary(run_id,action,body):
        result=original(run_id,action,body)
        if action=="SIDE_EFFECT_PREPARED":service.request(run_id,principal_id="owner")
        return result
    monkeypatch.setattr(ops["repo"],"audit",cancel_at_boundary)
    with pytest.raises(EffectUncertain):deploy(ops)
    assert ops["provider"].sent==[]
    assert service.settle("r",principal_id="owner",actor_id="ops").status is RunStatus.CANCELLED


@pytest.mark.ac("AC-24", "AC-42")
def test_late_deploy_response_does_not_overwrite_confirmed_rollback(ops):
    ops["provider"].unhealthy=True
    deployment=deploy(ops);ops["coordinator"].finalize(deployment.deployment_id,actor_id="ops")
    original=next(e for e in ops["store"].runtime_list("effect") if e["action"]=="DEPLOY")
    observation=DeploymentObservation.model_validate(original["observation"])
    assert ops["executor"]._settle(original,observation).status is DeploymentStatus.ROLLED_BACK


@pytest.mark.ac("AC-42")
def test_cancellation_before_any_deployment_does_not_require_an_ops_snapshot(ops):
    service=CancellationService(ops["coordinator"]);service.request("r",principal_id="owner")
    assert service.settle("r",principal_id="owner",actor_id="unused-no-effects").status is RunStatus.CANCELLED
    assert not ops["provider"].sent


@pytest.mark.ac("AC-50")
def test_successful_rollback_without_healthy_environment_remains_unreconciled(ops,monkeypatch):
    ops["provider"].unhealthy=True
    original=ops["provider"].health
    def failed_health(expected):
        result=original(expected)
        if expected=="baseline":result["healthy"]=False
        return result
    monkeypatch.setattr(ops["provider"],"health",failed_health)
    deployment=deploy(ops)
    result=ops["coordinator"].finalize(deployment.deployment_id,actor_id="ops")
    assert result.status is RunStatus.NEEDS_RECONCILIATION
    assert ops["store"].pending_tool_executions("r")


@pytest.mark.ac("AC-50", "AC-57")
def test_unsent_rollback_after_expiry_can_receive_new_exact_recovery_permission(ops):
    ops["provider"].unhealthy=True
    deployment=deploy(ops)
    ops["clock"][0]+=timedelta(hours=2)
    result=ops["coordinator"].finalize(deployment.deployment_id,actor_id="ops")
    # 回滚许可过期是本地可判定拒绝：不产生 UNKNOWN 凭据，停在 BLOCKED 等待新许可后重试
    assert result.status is RunStatus.BLOCKED
    assert ops["provider"].sent==["DEPLOY"]
    assert not any(e["action"]=="ROLLBACK" for e in ops["store"].runtime_list("effect"))
    recovery=ops["store"].runtime_get("recovery",deployment.deployment_id)
    assert recovery["reason"]=="ROLLBACK_AUTHORIZATION_DENIED" and not recovery["safe"]
    request=ops["releases"].request(release_id=ops["release"].release_id,principal_id="owner",environment_id="staging",target_ids=["t"],
        action_scope=[ReleaseAction.ROLLBACK],now=ops["clock"][0])
    auth=ops["releases"].decide(request_id=request.authorization_request_id,principal_id="owner",decision=ApprovalDecision.APPROVE,now=ops["clock"][0])
    ops["executor"].rollback(deployment.deployment_id,actor_id="ops",authorization_id=auth.authorization_id)
    assert ops["coordinator"].recover(deployment.deployment_id,actor_id="ops").status is RunStatus.BLOCKED
    assert ops["provider"].sent==["DEPLOY","ROLLBACK"]


@pytest.mark.ac("AC-54")
def test_target_cannot_be_repointed_while_deployment_lease_is_active(ops):
    deploy(ops)
    changed=ops["target"].model_copy(update={"expected_text":"different"})
    with pytest.raises(PermissionError):ops["executor"].register_target(changed,principal_id="owner")


@pytest.mark.ac("AC-49", "AC-59")
def test_new_p1_during_deployment_rejects_g3_and_recovers_instead_of_hanging(ops):
    deployment=deploy(ops)
    from agentloop.core.contracts.models import Issue
    artifact=ops["repo"].audit("r","NEW_SECURITY_PROOF",{"risk":"high"})
    ops["store"].put_issue(Issue(issue_id="new-p1",run_id="r",severity=Severity.CRITICAL,category=IssueCategory.SECURITY_FINDING,
        description="new finding while request was in flight",evidence_artifact_ids=[artifact.artifact_id]))
    result=ops["coordinator"].finalize(deployment.deployment_id,actor_id="ops")
    assert result.status is RunStatus.BLOCKED
    assert ops["store"].latest_gate_result("r","G3").status is GateStatus.REJECTED
    assert ops["provider"].current=="baseline"


@pytest.mark.ac("AC-49", "AC-57")
def test_approver_revoked_after_dispatch_does_not_produce_a_g3_pass(ops):
    deployment=deploy(ops)
    principal=ops["store"].get_principal("owner");principal.status="DISABLED";ops["store"].put_principal(principal)
    result=ops["coordinator"].finalize(deployment.deployment_id,actor_id="ops")
    # 签发人失效导致回滚被本地拒绝：外部状态已知，不进入"副作用未知"，停在 BLOCKED
    assert result.status is RunStatus.BLOCKED
    assert ops["store"].latest_gate_result("r","G3").status is GateStatus.REJECTED
    assert ops["provider"].sent==["DEPLOY"]


@pytest.mark.ac("AC-54", "AC-56")
def test_revocation_between_prepare_and_dispatch_blocks_send(ops, monkeypatch):
    """prepare→dispatch 窗口内撤销授权：不得发出外部请求。"""
    releases = ops["releases"]
    original = ops["repo"].audit
    def revoke_at_boundary(run_id, action, body):
        result = original(run_id, action, body)
        if action == "SIDE_EFFECT_PREPARED":
            releases.revoke(ops["authorization"].authorization_id, "owner")
        return result
    monkeypatch.setattr(ops["repo"], "audit", revoke_at_boundary)
    with pytest.raises(EffectUncertain): deploy(ops)
    assert ops["provider"].sent == []
    effect = ops["store"].runtime_list("effect")[0]
    assert effect["state"] == "CANCELLED" and effect.get("dispatched") is False
    assert ops["store"].deployments_for("r")[0].status is DeploymentStatus.FAILED
    assert ops["store"].get_release(ops["release"].release_id).status is ReleaseStatus.READY
    assert ops["store"].runtime_get("target_lease", "p/t")["active"] is False
    assert not ops["store"].pending_tool_executions("r")


@pytest.mark.ac("AC-50", "AC-57")
def test_reconcile_of_never_dispatched_effect_settles_cancelled_and_frees_target(ops, monkeypatch):
    """凭据落库后进程崩溃（请求从未发送）：对账可确定收敛为取消并释放目标租约。"""
    deployment = deploy(ops)
    effect = next(e for e in ops["store"].runtime_list("effect"))
    effect["state"] = "PREPARED"; effect["dispatched"] = False
    ops["store"].runtime_put("effect", effect["id"], effect)
    receipt = ops["store"].find_tool_execution_by_key(effect["idempotency_key"])
    receipt.status = ToolExecutionStatus.STARTED; ops["store"].put_tool_execution(receipt)
    monkeypatch.setattr(ops["provider"], "query",
        lambda op: DeploymentObservation(operation_id=op, status="NOT_FOUND"))
    result = ops["executor"].reconcile(effect["id"], principal_id="owner")
    assert result.deployment_id == deployment.deployment_id
    assert ops["store"].runtime_get("effect", effect["id"])["state"] == "CANCELLED"
    assert ops["store"].find_tool_execution_by_key(effect["idempotency_key"]).status is ToolExecutionStatus.CANCELLED
    assert ops["store"].runtime_get("target_lease", "p/t")["active"] is False
    assert ops["store"].get_release(deployment.release_id).status is ReleaseStatus.READY


@pytest.mark.ac("AC-50", "AC-57")
def test_first_deploy_failure_without_baseline_verifies_target_and_unblocks(ops, monkeypatch):
    """首次部署失败且无回滚基线：不盲试回滚，用健康检查证明目标未上线后安全收敛。"""
    def failed_deploy(operation_id, action, *, bundle, artifact_digest, previous_digest=None):
        return DeploymentObservation(operation_id=operation_id, status="FAILED",
                                     artifact_digest=None, previous_digest=None)
    monkeypatch.setattr(ops["provider"], "execute", failed_deploy)
    deployment = deploy(ops)
    assert deployment.status is DeploymentStatus.FAILED
    result = ops["coordinator"].finalize(deployment.deployment_id, actor_id="ops")
    assert (result.phase, result.status) == (RunPhase.DEPLOYMENT_RECOVERY, RunStatus.BLOCKED)
    recovery = ops["store"].runtime_get("recovery", deployment.deployment_id)
    assert recovery["safe"] is True and recovery["previous_digest"] == "baseline"
    assert ops["store"].get_release(deployment.release_id).status is ReleaseStatus.READY
    assert ops["store"].runtime_get("target_lease", "p/t")["active"] is False
    ops["coordinator"].remediate(deployment.deployment_id, cause="ENV_DEFECT", principal_id="owner")
    assert ops["store"].get_run("r").status is RunStatus.WAITING_APPROVAL


@pytest.mark.ac("AC-50")
def test_unverifiable_first_deploy_failure_waits_for_manual_reconciliation(ops, monkeypatch):
    """提供方报告失败但目标实际在线上产物：无法证明安全，停在 BLOCKED 等待人工。"""
    def failed_deploy(operation_id, action, *, bundle, artifact_digest, previous_digest=None):
        return DeploymentObservation(operation_id=operation_id, status="FAILED",
                                     artifact_digest=None, previous_digest=None)
    monkeypatch.setattr(ops["provider"], "execute", failed_deploy)
    live = bundle_digest(ops["bundle"])
    monkeypatch.setattr(ops["provider"], "health",
        lambda expected: {"artifact_digest": live, "healthy": False, "evidence": "FAULT INJECTION FIXTURE ONLY"})
    deployment = deploy(ops)
    result = ops["coordinator"].finalize(deployment.deployment_id, actor_id="ops")
    assert (result.phase, result.status) == (RunPhase.DEPLOYMENT_RECOVERY, RunStatus.BLOCKED)
    recovery = ops["store"].runtime_get("recovery", deployment.deployment_id)
    assert recovery["safe"] is False and recovery["reason"] == "NO_ROLLBACK_BASELINE_UNVERIFIED"
    with pytest.raises(Exception):
        ops["coordinator"].remediate(deployment.deployment_id, cause="ENV_DEFECT", principal_id="owner")
