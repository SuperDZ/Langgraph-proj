"""多角色研发演示；发布包由可信打包器生成，绝不使用 Commit 代替产物摘要。"""
import json
from pathlib import Path
import shutil
from html.parser import HTMLParser
from langgraph.types import interrupt
from .scripted import ScriptedDemoAdapter
from ..core.department_graphs.delivery import DeliveryWorkflow, WorkflowBlocked
from ..core.contracts.phase3 import StaticServiceConfig
from ..core.contracts.enums import RunStatus, TrustLevel
from ..core.runtime.configuration import digest


def prepare_fixture(data_dir):
    fixture=Path(data_dir)/"phase3-fixture"
    if not fixture.exists():
        shutil.copytree(Path(__file__).parent/"spring-bug",fixture)
        (fixture/"web").mkdir(); (fixture/"deploy").mkdir()
        (fixture/"web/index.html").write_text("<!doctype html><title>AgentLoop baseline</title>AgentLoop baseline",encoding="utf-8")
        (fixture/"deploy/service.json").write_text('{"service":"baseline"}',encoding="utf-8")
    return fixture


class Phase3ScriptedAdapter(ScriptedDemoAdapter):
    def invoke(self,role,context,schema):
        if role in {"frontend","devops"}:
            content = '<!doctype html><html lang="zh-CN"><title>AgentLoop delivery</title><main><h1>AgentLoop</h1><p>Multi-role delivery verified.</p></main></html>' if role=="frontend" else json.dumps(StaticServiceConfig().model_dump(mode="json"))
            return {"summary":f"{role} candidate","changes":[{"path":path,"expected_sha256":context["hashes"][path],"content":content} for path in context["sources"]]}
        return super().invoke(role,context,schema)


class MultiRoleRunner:
    def __init__(self,delegate): self.delegate=delegate
    def run(self,workspace,*,attempt):
        report=self.delegate.run(workspace,attempt=attempt)
        checks=[]
        try:
            html=(workspace.root/"web/index.html").read_text(encoding="utf-8")
            parser=HTMLParser(); parser.feed(html); parser.close()
            checks.append({"name":"frontend_document", "passed":"<main>" in html and "<title>" in html and "AgentLoop" in html})
            StaticServiceConfig.model_validate_json((workspace.root/"deploy/service.json").read_text(encoding="utf-8"))
            checks.append({"name":"deployment_schema","passed":True})
        except (ValueError,OSError): checks.append({"name":"deployment_schema","passed":False})
        report["integration_checks"]=checks
        if not all(c["passed"] for c in checks): report["decision"]="FAIL"
        return report


class Phase3DeliveryWorkflow(DeliveryWorkflow):
    def _release_wait(self,state):
        self.workspace.assert_revision(state["commit_sha"])
        config=StaticServiceConfig.model_validate_json((self.workspace.root/"deploy/service.json").read_text(encoding="utf-8"))
        bundle={"files":{"index.html":(self.workspace.root/config.document).read_text(encoding="utf-8")},"commit":state["commit_sha"]}
        artifact=self.archive.put(run_id=state["run_id"],kind="RELEASE_BUNDLE",producer="release-packager",value=bundle,trust=TrustLevel.VERIFIED_INTERNAL)
        release=self.releases.create(run_id=state["run_id"],commit_sha=state["commit_sha"],artifact_digest=artifact.sha256)
        self.store.runtime_put("release_bundle",release.release_id,{"artifact_id":artifact.artifact_id,"digest":artifact.sha256})
        run=self.store.get_run(state["run_id"])
        if run.status is not RunStatus.WAITING_APPROVAL:
            self.transitions.transition(run.run_id,target_status=RunStatus.WAITING_APPROVAL,expected_version=run.state_version)
        interrupt({"kind":"REAL_RELEASE_AUTHORIZATION","release_id":release.release_id,"artifact_digest":artifact.sha256})
        raise WorkflowBlocked("Phase 3 发布必须通过独立执行器")

    def summary(self,run_id):
        result=super().summary(run_id)
        result["mode"]="ISOLATED_MULTI_ROLE_WORKTREES_CONTROLLED_DEPLOYMENT"
        return result

    def sync_delivery_checkpoint(self,run_id,deployment_id):
        if self.store.get_run(run_id).status is not RunStatus.COMPLETED: raise ValueError("交付尚未完成")
        self.graph.update_state(self._config(run_id),{"deployment_id":deployment_id},as_node="simulate_deployment")

    def resume_rework(self,run_id):
        from ..core.contracts.enums import RunPhase
        run=self.store.get_run(run_id)
        snapshot=self.graph.get_state(self._config(run_id)); values=dict(snapshot.values)
        if run.status is not RunStatus.RUNNING: raise ValueError("返工状态未就绪")
        if run.phase is RunPhase.ENGINEERING:
            self.graph.update_state(self._config(run_id),{"previous_failure":"G3 code remediation"},as_node="g1")
        elif run.phase in {RunPhase.PRODUCT,RunPhase.ARCHITECTURE}:
            # 产品/架构版本需重新审批，不沿用原 G1。
            if run.phase is RunPhase.ARCHITECTURE:
                self.transitions.transition(run_id,target_phase=RunPhase.PRODUCT,target_status=RunStatus.RUNNING)
            self.graph.update_state(self._config(run_id),{"previous_failure":"G3 upstream remediation","front_accepted":False},as_node="front_expert")
        else: raise ValueError("该阶段不属于上游返工")
        return self._invoke(run_id,None)
