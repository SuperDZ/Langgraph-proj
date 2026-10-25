"""Phase 1 演示组装；工具链和模型配置属于受信应用输入。"""

from datetime import timedelta
import os
from pathlib import Path
import re
import shutil

from ..core.approvals import RBACService
from ..core.contracts.delivery import WorkflowConfig
from ..core.contracts.enums import PrincipalType
from ..core.contracts.models import utc_now
from ..core.department_graphs.delivery import DeliveryWorkflow
from ..core.orchestration import SQLiteStore
from ..core.runtime.testing import SurefireRunner
from ..core.runtime.workspace import GitWorkspace
from ..core.runtime.workers import WorkerRuntime
from ..knowledge.archive import ArtifactArchive
from .scripted import ScriptedDemoAdapter, ScriptedSecurityRepairAdapter

EDITABLE_PATH = "src/main/java/example/HelloController.java"
REQUIRED_TESTS = {"missingNameReturns400", "emptyNameReturns400", "blankNameReturns400", "validNamePreservesGreeting"}


def build_demo(*, data_dir, run_id, java_home=None, maven=None, require_confirmation=False, runner=None, adapter=None,
               security_example=False, runtime_config=None, transports=None, preflight=True, phase3=False, checkpoint_only=False):
    if not re.fullmatch(r"[A-Za-z0-9_-]{1,80}", run_id):
        raise ValueError("Run ID 只能包含字母、数字、下划线和连字符")
    data_dir = Path(data_dir).resolve()
    data_dir.mkdir(parents=True, exist_ok=True)
    store = SQLiteStore(data_dir / "state.db")
    try:
        config = WorkflowConfig.model_validate_json((Path(__file__).parent / "phase1-config.json").read_text(encoding="utf-8"))
        config.require_confirmation = require_confirmation
        if security_example:
            config.role_profiles["backend"] = "scripted-security-demo"
        fixture=Path(__file__).parent / "spring-bug"
        editable=[EDITABLE_PATH]
        if phase3:
            from .phase3 import prepare_fixture, Phase3ScriptedAdapter
            fixture=prepare_fixture(data_dir)
            editable += ["web/index.html","deploy/service.json"]
            config.changes_ui=True
            config.role_profiles.update({"frontend":"scripted-phase3","devops":"scripted-phase3"})
        workspace = GitWorkspace.from_fixture(fixture, data_dir / run_id / "workspace", editable_paths=editable)
        archive = ArtifactArchive(data_dir / "artifacts", store)
        if store.find_run(run_id) is not None:
            snapshots = [a for a in store.artifacts_for(run_id) if a.type == "CONFIG_SNAPSHOT"]
            if not snapshots:
                raise ValueError("缺少原始配置快照")
            config = WorkflowConfig.model_validate(archive.read(snapshots[0].artifact_id, run_id=run_id))
            mode=store.runtime_get("workflow_mode",run_id)
            expected_mode="phase3" if phase3 else "phase2" if runtime_config is not None else "phase1"
            if not mode:
                from ..core.runtime.workers import mode_from_profiles
                mode={"mode":mode_from_profiles(config.role_profiles)}
            if mode and mode["mode"]!=expected_mode:raise ValueError("恢复命令的运行模式与原 Run 不一致")
        workers = WorkerRuntime(store=store, archive=archive, profiles=config.role_profiles,
                                adapters={"scripted-demo": adapter or ScriptedDemoAdapter(),
                                          "scripted-security-demo": ScriptedSecurityRepairAdapter()})
        if phase3:
            workers.adapters["scripted-phase3"]=Phase3ScriptedAdapter()
        if checkpoint_only:
            from ..core.contracts.enums import RunStatus
            existing=store.find_run(run_id)
            if existing is None or existing.status is not RunStatus.COMPLETED:
                raise ValueError("仅已完成的 Run 允许终态 checkpoint 同步")
            class NoWorker:
                def invoke(self,*args,**kwargs): raise ValueError("checkpoint 同步不能执行 Worker")
            workers.adapters.update({profile:NoWorker() for profile in config.role_profiles.values()})
        if runner is None:
            home = Path(java_home or os.environ.get("JAVA_HOME", "")).resolve()
            if not (home / "bin" / ("java.exe" if os.name == "nt" else "java")).is_file():
                raise ValueError("请通过 --java-home 指定 JDK 21")
            executable = maven or shutil.which("mvn")
            if not executable:
                raise ValueError("Maven 不存在，请通过 --maven 指定")
            settings = data_dir / "maven-settings.xml"
            settings.write_text('<settings xmlns="http://maven.apache.org/SETTINGS/1.2.0"><mirrors><mirror>'
                '<id>central-only</id><mirrorOf>*</mirrorOf><url>https://repo.maven.apache.org/maven2</url>'
                '</mirror></mirrors></settings>', encoding="utf-8")
            inherited = {"SYSTEMROOT", "WINDIR", "COMSPEC", "TEMP", "TMP", "USERPROFILE", "HOME", "APPDATA",
                         "LOCALAPPDATA", "PATH", "PATHEXT", "LANG", "LC_ALL"}
            env = {key: value for key, value in os.environ.items() if key.upper() in inherited}
            env.update({"JAVA_HOME": str(home), "PATH": str(home / "bin") + os.pathsep + os.environ.get("PATH", "")})
            repository = Path(os.environ.get("AGENTLOOP_MAVEN_REPOSITORY", str(data_dir / "m2"))).resolve()
            runner = SurefireRunner(argv=[str(executable), "-s", str(settings), "-gs", str(settings), f"-Dmaven.repo.local={repository}", "-B", "-ntp"],
                                     environment=env, required_tests=REQUIRED_TESTS)
        rbac = RBACService(store)
        rbac.register_principal("demo-owner", PrincipalType.HUMAN_USER, "demo://fake-human")
        for role in ("project_owner", "release_approver"):
            if role not in rbac.roles_of("demo-owner", config.project_id):
                rbac.bind_role(principal_id="demo-owner", role_id=role, scope_type="project", scope_id=config.project_id,
                               valid_from=utc_now() - timedelta(seconds=1))
        if runtime_config is not None:
            from ..core.runtime.configuration import RuntimeRepository, effective_config, digest
            from ..core.runtime.models import ManagedModelRuntime
            from ..core.runtime.skills import SkillRegistry
            from ..core.runtime.mcp import MCPRegistry
            if set(config.role_profiles) != set(runtime_config.roles):
                raise ValueError("Phase 2 配置必须覆盖全部工作流角色")
            repo = RuntimeRepository(store, archive)
            skills, tools = SkillRegistry(repo, rbac), MCPRegistry(repo, rbac)
            managed = ManagedModelRuntime(repo, transports=transports, skills=skills, tools=tools)
            effective = {role: effective_config(runtime_config, role) for role in runtime_config.roles}
            profiles = {role: "managed:" + digest(value.model_dump(mode="json")) for role, value in effective.items()}
            if store.find_run(run_id) is not None and config.role_profiles != profiles:
                raise ValueError("恢复必须使用原始 Phase 2 配置")
            config.role_profiles = profiles
            if preflight:
                managed.preflight(effective.values())
            workers = WorkerRuntime(store=store, archive=archive, profiles=profiles,
                adapters={name: managed for name in profiles.values()}, managed=managed, runtime_config=runtime_config)
        workflow_type=DeliveryWorkflow
        coordinator=None
        if phase3:
            from .phase3 import Phase3DeliveryWorkflow, MultiRoleRunner
            from ..core.runtime.configuration import RuntimeRepository
            from ..core.runtime.parallel import ParallelEngineering
            workflow_type=Phase3DeliveryWorkflow
            coordinator=ParallelEngineering(RuntimeRepository(store,archive),workspace,workers,data_dir/run_id/"worktrees")
            runner=MultiRoleRunner(runner)
        workflow = workflow_type(store=store, archive=archive, workspace=workspace, workers=workers, runner=runner,
            config=config, rbac=rbac, checkpoint_path=data_dir / "delivery-checkpoints.db",engineering_coordinator=coordinator)
        return workflow
    except BaseException:
        store.close()
        raise
