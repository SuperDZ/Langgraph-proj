"""真实多角色 Git/Maven/Spring → 授权 → HTTP 发布 → 巡检闭环。"""
import os
from datetime import timedelta
import pytest
from agentloop.examples.demo import build_demo
from agentloop.phase3_cli import local_identities
from agentloop.core.approvals.releases import ReleaseService
from agentloop.core.contracts.enums import *
from agentloop.core.contracts.phase3 import DeploymentTarget,ExecutionPolicy
from agentloop.core.runtime.configuration import RuntimeRepository
from agentloop.core.runtime.effects import SideEffectExecutor
from agentloop.core.runtime.operations import DeploymentCoordinator,MaintenanceService
from agentloop.core.runtime.deployment_providers import LocalStaticProvider

pytestmark=[pytest.mark.java_integration,pytest.mark.skipif(os.environ.get("AGENTLOOP_RUN_JAVA")!="1",reason="需启用 Java 21/Maven"),
    pytest.mark.ac("AC-43","AC-54","AC-56"),pytest.mark.requirements("REQ-009","REQ-010","REQ-014","REQ-015","REQ-017","REQ-035","REQ-044")]


def test_real_multi_role_delivery_authorized_http_publish_and_periodic_check(tmp_path):
    workflow=build_demo(data_dir=tmp_path,run_id="phase3-integration",phase3=True,
        java_home=os.environ.get("AGENTLOOP_JAVA_HOME"),maven=os.environ.get("AGENTLOOP_MAVEN"))
    provider=None
    try:
        summary=workflow.start("phase3-integration","修复参数边界并交付页面和部署配置")
        assert (summary["phase"],summary["status"])==("RELEASE_AUTHORIZATION","WAITING_APPROVAL"),summary
        reports=[workflow.archive.read(a.artifact_id,run_id="phase3-integration") for a in workflow.store.artifacts_for("phase3-integration") if a.type=="TEST_EXECUTION"]
        assert [r["decision"] for r in reports]==["FAIL","PASS"]
        assert reports[-1]["failed"]==0 and reports[-1]["total"]==4
        assert all(c["passed"] for c in reports[-1]["integration_checks"])
        local_identities(workflow.rbac,workflow.config.project_id)
        repo=RuntimeRepository(workflow.store,workflow.archive)
        executor=SideEffectExecutor(repo,service_principal="phase3-executor",providers={})
        target=DeploymentTarget(target_id="staging",project_id=workflow.config.project_id,environment="staging",provider="local-static")
        executor.register_target(target,principal_id="demo-owner")
        executor.bind_policy("phase3-integration",ExecutionPolicy(principal_id="operations-expert",role="operations-expert",
            platform=["cap.deploy.staging"],department=["cap.deploy.staging"],agent=["cap.deploy.staging"],task=["cap.deploy.staging"],target_ids=["staging"]),principal_id="demo-owner")
        release=workflow.store.releases_for("phase3-integration")[-1]
        service=ReleaseService(workflow.store,executor.transitions,workflow.rbac)
        request=service.request(release_id=release.release_id,principal_id="demo-owner",environment_id="staging",target_ids=["staging"],action_scope=[ReleaseAction.DEPLOY,ReleaseAction.ROLLBACK])
        authorization=service.decide(request_id=request.authorization_request_id,principal_id="demo-owner",decision=ApprovalDecision.APPROVE)
        provider=LocalStaticProvider(tmp_path/"target",target);executor.providers["staging"]=provider
        saved=workflow.store.runtime_get("release_bundle",release.release_id)
        bundle=workflow.archive.read(saved["artifact_id"],run_id="phase3-integration")
        deployment=executor.execute(run_id="phase3-integration",actor_id="operations-expert",authorization_id=authorization.authorization_id,
            target_id="staging",bundle=bundle,idempotency_key="authorized-release")
        result=DeploymentCoordinator(executor).finalize(deployment.deployment_id,actor_id="operations-expert")
        assert result.status is RunStatus.COMPLETED
        workflow.sync_delivery_checkpoint(result.run_id,deployment.deployment_id)
        assert workflow.summary(result.run_id)["checkpoint_next"]==[]
        maintenance=MaintenanceService(executor)
        maintenance.schedule(result.run_id,"staging",principal_id="demo-owner",interval_seconds=60)
        before=workflow.store.get_run(result.run_id)
        assert maintenance.tick()[0].status is RunStatus.COMPLETED
        assert workflow.store.get_run(result.run_id)==before
    finally:
        if provider:provider.close()
        workflow.close();workflow.store.close()
