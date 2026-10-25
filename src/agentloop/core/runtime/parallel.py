"""隔离 Git Worktree 与可恢复的串行集成；冲突不触碰主工作区。"""
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
import os
import subprocess
from ..contracts.delivery import PatchProposal
from ..contracts.phase3 import WorkerTask
from ..contracts.enums import IssueCategory, IssueStatus, RunPhase, RunStatus, Severity, TrustLevel
from ..contracts.models import Issue
from ..routing import LoopRouter
from .workspace import GitWorkspace, file_digest
from .configuration import digest


class MergeBlocked(ValueError): pass


class WorktreeIntegration:
    def __init__(self, repository, workspace, root):
        self.repo, self.store, self.workspace = repository, repository.store, workspace
        self.root = Path(root).resolve(); self.root.mkdir(parents=True, exist_ok=True)
        if self.root == workspace.root or self.root.is_relative_to(workspace.root):
            raise ValueError("Worker Worktree 不能放在集成工作区内")
        self.router = LoopRouter(self.store)

    def _running(self, run_id):
        run = self.store.get_run(run_id)
        if run.phase is not RunPhase.ENGINEERING or run.status is not RunStatus.RUNNING:
            raise ValueError("仅运行中的研发阶段接受修改和合并")

    def _blob(self,commit,path):
        result=subprocess.run(["git","-c","core.hooksPath=NUL" if os.name=="nt" else "core.hooksPath=/dev/null",
            "-C",str(self.workspace.root),"show",commit+":"+path],capture_output=True,check=True,timeout=30)
        return result.stdout.decode("utf-8").replace("\r\n","\n")

    def prepare(self, run_id, task, base):
        self._running(run_id)
        if not set(task.editable_paths) <= self.workspace.editable_paths:
            raise PermissionError("任务修改范围超过受信工作区")
        key = f"{run_id}/{task.task_id}"
        path = self.root / digest(run_id)[:16] / task.task_id
        branch = f"codex/{digest(run_id)[:12]}-{task.task_id}"
        with self.store.transaction():
            record = self.store.runtime_get("worktree_task", key)
            if record:
                if record["task"] != task.model_dump(mode="json") or record["base"] != base:
                    raise ValueError("任务定义或基础 Commit 已改变")
            else:
                if path.exists(): raise PermissionError("拒绝接管已有目录")
                record = {"key": key, "run_id": run_id, "task": task.model_dump(mode="json"), "base": base,
                          "path": str(path), "branch": branch, "state": "CREATING"}
                self.store.runtime_put("worktree_task", key, record)
        if not path.exists():
            path.parent.mkdir(parents=True, exist_ok=True)
            self.workspace.git("worktree", "add", "-b", branch, str(path), base)
        worker = GitWorkspace(path, editable_paths=task.editable_paths)
        if record["state"] == "CREATING":
            worker.assert_revision(base)
            record["state"] = "READY"; self.store.runtime_put("worktree_task", key, record)
        return worker, record

    def apply(self, run_id, task, proposal, base):
        worker, record = self.prepare(run_id, task, base)
        if record["state"] in {"COMMITTED", "MERGED"}: return record["commit"]
        self._running(run_id)
        receipt = self.store.runtime_get("worktree_patch", record["key"])
        body = proposal.model_dump(mode="json")
        if receipt and receipt != body: raise ValueError("同一任务不得替换持久候选补丁")
        self.store.runtime_put("worktree_patch", record["key"], body)
        with self.store.transaction():
            self._running(run_id)
            commit = worker.apply(proposal, attempt=task.task_id)
        record.update(state="COMMITTED", commit=commit)
        self.store.runtime_put("worktree_task", record["key"], record)
        self.repo.audit(run_id,"WORKTREE_COMMITTED", {"task_id":task.task_id,"role":task.role,"base":base,"commit":commit})
        return commit

    def merge(self, run_id, task_id):
        self._running(run_id)
        key = f"{run_id}/{task_id}"
        with self.store.transaction():
            self._running(run_id)
            record = self.store.runtime_get("worktree_task", key)
            if record["state"] == "MERGED":
                return record["merged_commit"]
            lease = self.store.runtime_get("integration_lease", str(self.workspace.root))
            if lease and lease["task"] != key: raise MergeBlocked("另一合并需先恢复")
            if record["state"] != "PREPARED":
                if record["state"] != "COMMITTED": raise MergeBlocked("任务未提交或存在冲突")
                task = WorkerTask.model_validate(record["task"])
                worker = GitWorkspace(record["path"], editable_paths=task.editable_paths)
                worker.assert_revision(record["commit"])
                changed = set(worker.git("diff","--name-only",record["base"],record["commit"]).splitlines())
                if not changed <= set(task.editable_paths): raise PermissionError("子分支夹带范围外修改")
                old = self.workspace.commit(); self.workspace.assert_revision(old)
                try:
                    tree = self.workspace.git("merge-tree","--write-tree",old,record["commit"]).splitlines()[0]
                except subprocess.CalledProcessError as exc:
                    if exc.returncode != 1: raise
                    artifact = self.repo.archive.put(run_id=run_id,kind="MERGE_CONFLICT",producer="git-integration",
                        trust=TrustLevel.VERIFIED_INTERNAL, value={"task":task_id,"base":record["base"],"head":old,"incoming":record["commit"],"details":exc.stdout[-12000:]})
                    record.update(state="CONFLICT", conflict_id=artifact.artifact_id, conflict_head=old)
                    self.store.runtime_put("worktree_task",key,record)
                    self.router.route(Issue(issue_id="merge-"+digest(key),run_id=run_id,category=IssueCategory.MERGE_CONFLICT,
                        severity=Severity.HIGH,description="Git 三方合并冲突，不能覆盖集成结果",evidence_artifact_ids=[artifact.artifact_id]),source_event_id=artifact.artifact_id)
                    return None
                merged = old if old == record["commit"] else self.workspace.git("commit-tree",tree,"-p",old,"-p",record["commit"],"-m",f"Integrate {task_id}")
                record.update(state="PREPARED", previous_head=old, merged_commit=merged)
                self.store.runtime_put("worktree_task",key,record)
                self.store.runtime_put("integration_lease",str(self.workspace.root),{"task":key})
        # PREPARED 已提交；Git 与数据库之间中断后，凭据仍能用于恢复。
        with self.store.transaction():
            self._running(run_id)
            current = self.workspace.commit()
            if current not in {record["previous_head"],record["merged_commit"]}: raise MergeBlocked("集成 HEAD 被外部修改")
            changed = self.workspace.git("diff","--name-only",record["previous_head"],record["merged_commit"]).splitlines()
            dirty = set(self.workspace.git("diff","HEAD","--name-only").splitlines()) | set(self.workspace.git("diff","--cached","--name-only").splitlines())
            if dirty - set(changed) or self.workspace.git("ls-files","--others","--exclude-standard"):
                raise MergeBlocked("集成工作区出现未知修改")
            for path in changed:
                actual = (self.workspace.root/path).read_text(encoding="utf-8")
                old_text = self._blob(record["previous_head"],path)
                new_text = self._blob(record["merged_commit"],path)
                if actual not in {old_text,new_text}: raise MergeBlocked("恢复不能覆盖其他编辑")
            if current == record["previous_head"]:
                self.workspace.git("update-ref","HEAD",record["merged_commit"],record["previous_head"])
            self.workspace.git("reset","--hard",record["merged_commit"])
            record["state"]="MERGED"; self.store.runtime_put("worktree_task",key,record)
            self.store.runtime_put("integration_lease",str(self.workspace.root),{})
            artifact = self.repo.audit(run_id,"WORKTREE_INTEGRATED",{"task_id":task_id,"commit":record["merged_commit"],"retest_required":True})
            for issue in self.store.list_issues(run_id):
                if issue.issue_id=="merge-"+digest(key):
                    issue.status=IssueStatus.RESOLVED; issue.evidence_artifact_ids.append(artifact.artifact_id); self.store.put_issue(issue)
            return record["merged_commit"]

    def resolve(self, run_id, task_id, proposal):
        self._running(run_id)
        key=f"{run_id}/{task_id}"; record=self.store.runtime_get("worktree_task",key)
        if record["state"]!="CONFLICT" or self.workspace.commit()!=record["conflict_head"]:
            raise MergeBlocked("冲突上下文已改变，需要重新计算")
        task=WorkerTask.model_validate(record["task"])
        resolution=WorkerTask(task_id=task_id+"-resolution",role=task.role,editable_paths=task.editable_paths)
        resolved=self.apply(run_id,resolution,proposal,record["conflict_head"])
        tree=self.workspace.git("rev-parse",resolved+"^{tree}")
        commit=self.workspace.git("commit-tree",tree,"-p",record["conflict_head"],"-p",record["commit"],"-m",f"Resolve {task_id}")
        record.update(state="COMMITTED",base=record["conflict_head"],commit=commit)
        self.store.runtime_put("worktree_task",key,record)
        # 校验来源由 resolution worktree 提供，原分支留存冲突证据。
        record["path"]=str(self.root/digest(run_id)[:16]/resolution.task_id)
        worker=GitWorkspace(record["path"],editable_paths=task.editable_paths)
        worker.git("reset","--hard",commit)
        self.store.runtime_put("worktree_task",key,record)
        return self.merge(run_id,task_id)


class ParallelEngineering:
    def __init__(self, repository, workspace, workers, root):
        self.repo,self.workspace,self.workers=repository,workspace,workers
        self.integration=WorktreeIntegration(repository,workspace,root)

    def develop(self, state, architecture, plan):
        base=self.workspace.commit()
        group=f"{state['run_id']}/{state['attempt']}"
        saved=self.repo.store.runtime_get("engineering_group",group)
        if saved:
            if saved.get("final_commit"):
                self.workspace.assert_revision(saved["final_commit"]); return saved["final_commit"]
            base=saved["base"]
        else:
            self.repo.store.runtime_put("engineering_group",group,{"base":base})
        scope={"backend":["src/main/java/example/HelloController.java"],"frontend":["web/index.html"],"devops":["deploy/service.json"]}
        if not set(p for paths in scope.values() for p in paths)<=set(architecture["editable_paths"]): raise PermissionError("架构未批准全部角色修改范围")
        tasks=[WorkerTask(task_id=f"{role}-{state['attempt']}",role=role,editable_paths=paths) for role,paths in scope.items()]
        def execute(task):
            worker,record=self.integration.prepare(state["run_id"],task,base)
            if record["state"] in {"COMMITTED","MERGED"}: return
            saved_patch=self.repo.store.runtime_get("worktree_patch",record["key"])
            if saved_patch:
                proposal=PatchProposal.model_validate(saved_patch)
            else:
                context={"attempt":state["attempt"],"sources":{p:(worker.root/p).read_text(encoding="utf-8") for p in task.editable_paths},
                    "hashes":{p:file_digest(worker.root/p) for p in task.editable_paths},"plan":plan,"architecture":architecture,
                    "task_id":task.task_id,"feedback":state.get("previous_failure","")}
                if task.role=="frontend":
                    context["technical_acceptance"]={"required_elements":["main","title"],"health_marker":"AgentLoop"}
                elif task.role=="devops":
                    from ..contracts.phase3 import StaticServiceConfig
                    context["technical_acceptance"]={"configuration_schema":StaticServiceConfig.model_json_schema()}
                proposal,_=self.workers.call(run_id=state["run_id"],role=task.role,context=context,schema=PatchProposal)
            self.integration.apply(state["run_id"],task,proposal,base)
        with ThreadPoolExecutor(max_workers=3) as pool:
            list(pool.map(execute,tasks))
        for task in tasks:
            if self.integration.merge(state["run_id"],task.task_id) is None: raise MergeBlocked("合并冲突必须先处理")
        final=self.workspace.commit()
        self.repo.store.runtime_put("engineering_group",group,{"base":base,"final_commit":final})
        return final
