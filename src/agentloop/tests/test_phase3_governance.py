"""风险豁免、受信 HTTP 代理与发布请求的第三阶段验收。"""
import threading
import pytest
from agentloop.tests.test_phase3_operations import ops,deploy
from agentloop.core.approvals.waivers import RiskWaiverService,waiver_effective
from agentloop.core.contracts.enums import *
from agentloop.core.contracts.models import Issue,utc_now
from agentloop.core.contracts.phase3 import DeploymentTarget,ExecutionPolicy
from agentloop.core.runtime.deployment_providers import HTTPDeploymentProvider
from agentloop.deployment_agent import create_agent_server

pytestmark=pytest.mark.requirements("REQ-013","REQ-014","REQ-015","REQ-033","REQ-041","REQ-043","REQ-044","REQ-045","REQ-048")


@pytest.mark.ac("AC-41", "AC-52")
@pytest.mark.parametrize("severity",[Severity.LOW,Severity.MEDIUM,Severity.HIGH,Severity.CRITICAL])
def test_risk_waiver_approval_revoke_and_hard_risks_never_active(ops,severity):
    artifact=ops["repo"].audit("r","TEST_ISSUE_EVIDENCE",{"severity":severity.value})
    issue=Issue(issue_id="risk",run_id="r",severity=severity,category=IssueCategory.SECURITY_FINDING,
        description="risk for approval test",evidence_artifact_ids=[artifact.artifact_id])
    ops["store"].put_issue(issue)
    service=RiskWaiverService(ops["repo"],ops["executor"].rbac,ops["executor"].transitions)
    waiver=service.request("r",principal_id="owner",issue_ids=["risk"],rationale="bounded local exposure",controls="isolation and monitoring")
    with pytest.raises(Exception):service.decide(waiver.waiver_id,principal_id="ops",approve=True)
    if severity in {Severity.HIGH,Severity.CRITICAL}:
        with pytest.raises(ValueError):service.decide(waiver.waiver_id,principal_id="owner",approve=True)
        assert ops["store"].get_risk_waiver(waiver.waiver_id).status is RiskWaiverStatus.PENDING
    else:
        approved=service.decide(waiver.waiver_id,principal_id="owner",approve=True)
        assert waiver_effective(ops["store"],ops["executor"].rbac,approved,utc_now())
        service.revoke(waiver.waiver_id,principal_id="owner")
        assert ops["store"].latest_gate_result("r","G2").status is GateStatus.STALE


@pytest.mark.ac("AC-54", "AC-56")
def test_real_authenticated_http_agent_deploy_query_and_health(ops,tmp_path,monkeypatch):
    monkeypatch.setenv("AGENTLOOP_TEST_AGENT_KEY","only-local-test-agent-token")
    server,backend=create_agent_server(ops["target"],tmp_path/"agent-target",token_ref="env:AGENTLOOP_TEST_AGENT_KEY")
    thread=threading.Thread(target=server.serve_forever,daemon=True);thread.start()
    try:
        target=DeploymentTarget(target_id="t",project_id="p",environment="staging",provider="http-agent",
            endpoint=f"http://127.0.0.1:{server.server_port}",secret_ref="env:AGENTLOOP_TEST_AGENT_KEY")
        ops["executor"].register_target(target,principal_id="owner")
        # 原许可绑定本地目标；切换代理必须重新获得精确目标配置许可。
        with pytest.raises(PermissionError):deploy(ops)
        request=ops["releases"].request(release_id=ops["release"].release_id,principal_id="owner",environment_id="staging",
            target_ids=["t"],action_scope=[ReleaseAction.DEPLOY,ReleaseAction.ROLLBACK],now=ops["clock"][0])
        authorization=ops["releases"].decide(request_id=request.authorization_request_id,principal_id="owner",decision=ApprovalDecision.APPROVE,now=ops["clock"][0])
        policy=ops["store"].runtime_get("execution_policy","r/ops")
        rbac=ops["executor"].rbac
        from datetime import timedelta
        rbac.register_principal("remote-ops",PrincipalType.AGENT_SERVICE,"test://remote-ops")
        rbac.bind_role(principal_id="remote-ops",role_id="viewer",scope_type="project",scope_id="p",valid_from=ops["clock"][0]-timedelta(seconds=1))
        policy.update(principal_id="remote-ops",network_hosts=["127.0.0.1"],secrets=["env:AGENTLOOP_TEST_AGENT_KEY"])
        ops["executor"].bind_policy("r",ExecutionPolicy.model_validate(policy),principal_id="owner")
        provider=HTTPDeploymentProvider(target);ops["executor"].providers["t"]=provider
        deployment=deploy(ops,actor_id="remote-ops",authorization_id=authorization.authorization_id)
        assert provider.query(deployment.external_operation_id).status=="SUCCEEDED"
        assert ops["coordinator"].finalize(deployment.deployment_id,actor_id="remote-ops").status is RunStatus.COMPLETED
    finally:
        server.shutdown();server.server_close();thread.join(timeout=2);backend.close()


@pytest.mark.ac("AC-57")
def test_rejected_authorization_stays_blocked_and_new_request_is_reviewable(ops):
    request=ops["releases"].request(release_id=ops["release"].release_id,principal_id="owner",environment_id="staging",
        target_ids=["t"],action_scope=[ReleaseAction.DEPLOY])
    assert ops["releases"].decide(request_id=request.authorization_request_id,principal_id="owner",decision=ApprovalDecision.REJECT) is None
    assert ops["store"].get_run("r").status is RunStatus.BLOCKED
    assert not ops["provider"].sent
    new=ops["releases"].request(release_id=ops["release"].release_id,principal_id="owner",environment_id="staging",
        target_ids=["t"],action_scope=[ReleaseAction.DEPLOY])
    assert new.release_id==request.release_id and new.authorization_request_id!=request.authorization_request_id
    assert ops["store"].get_run("r").status is RunStatus.WAITING_APPROVAL


@pytest.mark.ac("AC-56")
def test_production_remains_disabled_without_explicit_host_enablement(ops):
    target=DeploymentTarget(target_id="t",project_id="p",environment="production",provider="http-agent",
        endpoint="https://deployment.invalid",secret_ref="env:AGENTLOOP_TEST_AGENT_KEY")
    ops["executor"].register_target(target,principal_id="owner")
    with pytest.raises(PermissionError,match="默认关闭"):deploy(ops)
    assert not ops["provider"].sent


@pytest.mark.ac("AC-56")
def test_production_capability_still_requires_release_permission_in_isolated_provider_fixture(ops):
    from datetime import timedelta
    rbac=ops["executor"].rbac
    target=DeploymentTarget(target_id="t",project_id="p",environment="production",provider="http-agent",
        endpoint="https://deployment.invalid",secret_ref="env:AGENTLOOP_TEST_AGENT_KEY")
    ops["executor"].register_target(target,principal_id="owner");ops["executor"].production_enabled=True
    with pytest.raises(PermissionError):deploy(ops,actor_id="backend")
    rbac.register_principal("production-ops",PrincipalType.AGENT_SERVICE,"test://production-ops")
    rbac.bind_role(principal_id="production-ops",role_id="viewer",scope_type="project",scope_id="p",valid_from=ops["clock"][0]-timedelta(seconds=1))
    policy=ops["store"].runtime_get("execution_policy","r/ops")
    policy.update(principal_id="production-ops",network_hosts=["deployment.invalid"],secrets=["env:AGENTLOOP_TEST_AGENT_KEY"])
    ops["executor"].bind_policy("r",ExecutionPolicy.model_validate(policy),principal_id="owner")
    with pytest.raises(PermissionError):deploy(ops,actor_id="production-ops")
    request=ops["releases"].request(release_id=ops["release"].release_id,principal_id="owner",environment_id="production",target_ids=["t"],
        action_scope=[ReleaseAction.DEPLOY,ReleaseAction.ROLLBACK],now=ops["clock"][0])
    authorization=ops["releases"].decide(request_id=request.authorization_request_id,principal_id="owner",decision=ApprovalDecision.APPROVE,now=ops["clock"][0])
    deployment=deploy(ops,actor_id="production-ops",authorization_id=authorization.authorization_id)
    assert deployment.environment_id=="production" and ops["provider"].sent==["DEPLOY"]
