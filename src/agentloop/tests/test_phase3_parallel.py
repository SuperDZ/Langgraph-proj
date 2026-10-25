"""真实 Git Worktree、合并冲突、断点恢复与多角色交付测试。"""
from pathlib import Path
import subprocess
import pytest
from agentloop.core.contracts.delivery import PatchProposal
from agentloop.core.contracts.enums import *
from agentloop.core.contracts.models import Run
from agentloop.core.contracts.phase3 import WorkerTask
from agentloop.core.orchestration import SQLiteStore
from agentloop.core.runtime.workspace import GitWorkspace,file_digest
from agentloop.core.runtime.configuration import RuntimeRepository
from agentloop.core.runtime.parallel import WorktreeIntegration
from agentloop.knowledge.archive import ArtifactArchive
from agentloop.examples.demo import build_demo
from agentloop.tests.test_ac_delivery import FakeTestRunner

pytestmark=pytest.mark.requirements("REQ-009","REQ-010","REQ-035","REQ-032","REQ-049")


@pytest.fixture
def integration(tmp_path):
    fixture=tmp_path/"fixture"; fixture.mkdir()
    (fixture/"a.txt").write_text("base\n"); (fixture/"b.txt").write_text("base\n")
    store=SQLiteStore(tmp_path/"state.db")
    store.put_run(Run(run_id="r",root_run_id="r",run_type=RunType.DELIVERY,project_id="p",phase=RunPhase.ENGINEERING,
        status=RunStatus.RUNNING,trigger_source="TEST",config_snapshot_id="c"))
    workspace=GitWorkspace.from_fixture(fixture,tmp_path/"integration",editable_paths=["a.txt","b.txt"])
    repository=RuntimeRepository(store,ArtifactArchive(tmp_path/"artifacts",store))
    yield WorktreeIntegration(repository,workspace,tmp_path/"workers")
    store.close()


def proposal(worker,path,text):
    return PatchProposal(summary="candidate",changes=[{"path":path,"expected_sha256":file_digest(worker.root/path),"content":text}])


@pytest.mark.ac("AC-43")
def test_isolated_branches_merge_disjoint_changes_and_require_final_retest(integration):
    base=integration.workspace.commit()
    first=WorkerTask(task_id="frontend",role="frontend",editable_paths=["a.txt"])
    second=WorkerTask(task_id="backend",role="backend",editable_paths=["b.txt"])
    a,_=integration.prepare("r",first,base); b,_=integration.prepare("r",second,base)
    assert a.root!=b.root and (integration.workspace.root/"a.txt").read_text()=="base\n"
    integration.apply("r",first,proposal(a,"a.txt","frontend\n"),base)
    integration.apply("r",second,proposal(b,"b.txt","backend\n"),base)
    integration.merge("r","frontend"); final=integration.merge("r","backend")
    assert (integration.workspace.root/"a.txt").read_text()=="frontend\n"
    assert (integration.workspace.root/"b.txt").read_text()=="backend\n"
    assert final==integration.workspace.commit()
    assert not integration.store.gate_results_for("r")


@pytest.mark.ac("AC-43")
def test_real_conflict_is_recorded_without_overwrite_then_resolved(integration):
    base=integration.workspace.commit()
    tasks=[WorkerTask(task_id=name,role="backend",editable_paths=["a.txt"]) for name in ("first","second")]
    for task in tasks:
        worker,_=integration.prepare("r",task,base)
        integration.apply("r",task,proposal(worker,"a.txt",task.task_id+"\n"),base)
    integration.merge("r","first")
    before=integration.workspace.commit()
    assert integration.merge("r","second") is None
    assert integration.workspace.commit()==before
    assert (integration.workspace.root/"a.txt").read_text()=="first\n"
    issue=integration.store.list_issues("r")[0]
    assert issue.category is IssueCategory.MERGE_CONFLICT and issue.routed_leader.value=="engineering-leader"
    resolved=integration.resolve("r","second",proposal(integration.workspace,"a.txt","first and second\n"))
    assert resolved==integration.workspace.commit()
    assert (integration.workspace.root/"a.txt").read_text()=="first and second\n"
    assert integration.store.list_issues("r")[0].status is IssueStatus.RESOLVED


@pytest.mark.ac("AC-24", "AC-43")
def test_git_ref_updated_but_database_not_committed_is_recovered(integration,monkeypatch):
    base=integration.workspace.commit(); task=WorkerTask(task_id="worker",role="backend",editable_paths=["a.txt"])
    worker,_=integration.prepare("r",task,base)
    integration.apply("r",task,proposal(worker,"a.txt","updated\n"),base)
    original=integration.workspace.git
    def fail(*args):
        if args[:2]==("reset","--hard"): raise OSError("crash after update-ref")
        return original(*args)
    monkeypatch.setattr(integration.workspace,"git",fail)
    with pytest.raises(OSError): integration.merge("r","worker")
    monkeypatch.setattr(integration.workspace,"git",original)
    recovered=integration.merge("r","worker")
    assert recovered==integration.workspace.commit()
    assert (integration.workspace.root/"a.txt").read_text()=="updated\n"


@pytest.mark.ac("AC-24", "AC-43")
def test_merge_recovery_preserves_even_whitespace_only_external_edits(integration,monkeypatch):
    from agentloop.core.runtime.parallel import MergeBlocked
    base=integration.workspace.commit();task=WorkerTask(task_id="edit",role="backend",editable_paths=["a.txt"])
    worker,_=integration.prepare("r",task,base);integration.apply("r",task,proposal(worker,"a.txt","updated\n"),base)
    original=integration.workspace.git
    def fail(*args):
        if args[:2]==("reset","--hard"):raise OSError("crash before checkout")
        return original(*args)
    monkeypatch.setattr(integration.workspace,"git",fail)
    with pytest.raises(OSError):integration.merge("r","edit")
    monkeypatch.setattr(integration.workspace,"git",original)
    (integration.workspace.root/"a.txt").write_text("base\n\n")
    with pytest.raises(MergeBlocked):integration.merge("r","edit")
    assert (integration.workspace.root/"a.txt").read_text()=="base\n\n"


@pytest.mark.ac("AC-43")
def test_three_role_worktrees_feed_final_commit_review_and_tests(tmp_path):
    workflow=build_demo(data_dir=tmp_path,run_id="multi",runner=FakeTestRunner(),phase3=True)
    try:
        summary=workflow.start("multi","fix hello and deliver UI and deployment configuration")
        assert summary["phase"]=="RELEASE_AUTHORIZATION",summary
        assert summary["status"]=="WAITING_APPROVAL",summary
        tasks=workflow.store.runtime_list("worktree_task")
        assert {t["task"]["role"] for t in tasks}=={"backend","frontend","devops"}
        assert len({t["path"] for t in tasks})==6
        assert all(t["state"]=="MERGED" for t in tasks)
        reports=[workflow.archive.read(a.artifact_id,run_id="multi") for a in workflow.store.artifacts_for("multi") if a.type=="TEST_EXECUTION"]
        assert [r["decision"] for r in reports]==["FAIL","PASS"]
        assert all(item["passed"] for item in reports[-1]["integration_checks"])
        release=workflow.store.releases_for("multi")[-1]
        assert release.artifact_digest!=release.commit_sha
        assert workflow.store.runtime_get("release_bundle",release.release_id)
        assert workflow.store.runtime_get("workflow_mode","multi")=={"mode":"phase3"}
        with pytest.raises(ValueError,match="运行模式"):
            build_demo(data_dir=tmp_path,run_id="multi",runner=FakeTestRunner())
        from agentloop.core.runtime.simulation import SimulatedDeployment
        request=workflow.releases.request(release_id=release.release_id,principal_id="demo-owner",environment_id="simulation",
            target_ids=["local-simulator"],action_scope=[ReleaseAction.DEPLOY])
        auth=workflow.releases.decide(request_id=request.authorization_request_id,principal_id="demo-owner",decision=ApprovalDecision.APPROVE)
        with pytest.raises(PermissionError,match="模拟发布"):
            SimulatedDeployment(workflow.store,workflow.transitions,workflow.rbac).execute("multi",auth.authorization_id)
        assert not workflow.store.deployments_for("multi")
    finally:
        workflow.close();workflow.store.close()


@pytest.mark.ac("AC-11", "AC-59")
def test_frontend_dynamic_code_is_independently_rejected_then_repaired(tmp_path):
    from agentloop.examples.phase3 import Phase3ScriptedAdapter
    class UnsafeFirst(Phase3ScriptedAdapter):
        def invoke(self,role,context,schema):
            output=super().invoke(role,context,schema)
            if role=="frontend" and context["attempt"]<3:
                output["changes"][0]["content"]+="<script>eval('unsafe candidate')</script>"
            return output
    workflow=build_demo(data_dir=tmp_path,run_id="security",runner=FakeTestRunner(),phase3=True)
    workflow.workers.adapters["scripted-phase3"]=UnsafeFirst()
    try:
        summary=workflow.start("security","fix and inspect frontend safety")
        assert summary["phase"]=="RELEASE_AUTHORIZATION",summary
        assert [g.status for g in workflow.store.gate_results_for("security","G2")]==[GateStatus.REJECTED,GateStatus.PASSED]
        assert workflow.store.list_issues("security")[0].status is IssueStatus.RESOLVED
        assert not workflow.store.deployments_for("security")
    finally:workflow.close();workflow.store.close()
