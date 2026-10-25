"""Phase 2 本地命令；身份沿用本地 demo RBAC，不代表外部认证。"""

import argparse
import json
from pathlib import Path
from .core.contracts.phase2 import RuntimeConfig
from .core.orchestration import SQLiteStore
from .core.approvals import RBACService
from .core.runtime.configuration import RuntimeRepository, effective_config
from .core.runtime.budget import BudgetLedger
from .core.runtime.skills import SkillRegistry
from .core.runtime.mcp import MCPRegistry, ServerConfig
from .knowledge.archive import ArtifactArchive


def default_config():
    roles = json.loads((Path(__file__).parent / "examples/phase1-config.json").read_text())["role_profiles"]
    return {"models": {"primary": {"model": "deepseek-flash"}, "reasoning": {"model": "deepseek-v4-pro", "max_output_tokens": 8192,
        "temperature": None, "thinking": "enabled", "reasoning_effort": "low"}},
        "platform": {"primary": "primary", "fallbacks": [], "token_budget": 500_000, "cost_budget": 1_000_000,
            "max_steps": 60, "concurrency": 1, "prompt_version": "phase2-v1",
            "policy": {"policy_id": "platform-v1", "models": ["primary", "reasoning"], "tools": [],
                "capabilities": [], "workspace_roots": [], "network_hosts": ["api.deepseek.com"],
                "secrets": ["env:DEEPSEEK_API_KEY"], "requires_human_approval": True}},
        "departments": {name: {} for name in ("product", "expert", "engineering", "security")},
        "roles": {role: {"department": "engineering" if role in {"backend", "testing", "code-review", "engineering-leader"}
            else "security" if role == "security-expert" else "expert" if role in {"architecture-expert", "expert-leader", "product-expert"}
            else "product", "agent": {"primary": "reasoning"} if role == "testing" else {}} for role in roles},
        "run_token_budget": 1_000_000, "run_cost_budget": 2_000_000}


def main(argv=None):
    parser = argparse.ArgumentParser(description="Phase 2 模型/Skills/MCP 本地受控运行；发布仍为模拟")
    parser.add_argument("command", choices=["phase2-config", "phase2-preflight", "phase2-run", "phase2-status", "phase2-confirm",
        "phase2-authorize", "phase2-export", "phase2-resume", "phase2-budget-approve", "phase2-skill-import", "phase2-skill-download",
        "phase2-skill-git", "phase2-skill-approve", "phase2-skill-bind", "phase2-skill-list", "phase2-skill-disable",
        "phase2-skill-uninstall", "phase2-skill-export", "phase2-skill-diff", "phase2-mcp-register", "phase2-mcp-approve",
        "phase2-mcp-test", "phase2-mcp-disable", "phase2-mcp-uninstall", "phase2-mcp-list", "phase2-mcp-call", "phase2-mcp-call-approve"])
    parser.add_argument("--data-dir", type=Path, default=Path(".agentloop/phase2"))
    parser.add_argument("--run-id", default="phase2-run")
    parser.add_argument("--config", type=Path)
    parser.add_argument("--output", type=Path, default=Path("docs/phase2-delivery-evidence.json"))
    parser.add_argument("--path", type=Path)
    parser.add_argument("--version")
    parser.add_argument("--previous-version")
    parser.add_argument("--principal-id", default="demo-owner")
    parser.add_argument("--role", default="backend")
    parser.add_argument("--accepted-risk", action="append", default=[])
    parser.add_argument("--trusted-host", action="append", default=[])
    parser.add_argument("--url")
    parser.add_argument("--revision")
    parser.add_argument("--sha256")
    parser.add_argument("--server")
    parser.add_argument("--tool")
    parser.add_argument("--arguments", default="{}")
    parser.add_argument("--idempotency-key")
    parser.add_argument("--request-id")
    parser.add_argument("--tokens", type=int)
    parser.add_argument("--cost", type=int)
    parser.add_argument("--role-tokens", type=int)
    parser.add_argument("--role-cost", type=int)
    parser.add_argument("--java-home")
    parser.add_argument("--maven")
    parser.add_argument("--require-confirmation", action="store_true")
    args = parser.parse_args(argv)
    def emit(result):
        print(json.dumps(result, ensure_ascii=True, indent=2))
    if args.command == "phase2-config":
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(default_config(), ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        return emit({"config": str(args.output.resolve())})
    if args.command in {"phase2-run", "phase2-confirm", "phase2-authorize", "phase2-preflight", "phase2-resume"}:
        if not args.config:
            parser.error("必须提供 --config")
        config = RuntimeConfig.model_validate_json(args.config.read_text(encoding="utf-8"))
        from .examples.demo import build_demo
        workflow = build_demo(data_dir=args.data_dir, run_id=args.run_id, java_home=args.java_home, maven=args.maven,
            require_confirmation=args.require_confirmation, runtime_config=config,
            preflight=args.command in {"phase2-preflight", "phase2-run", "phase2-resume"})
        try:
            if args.command == "phase2-preflight":
                result = {"preflight": "PASSED", "roles": {role: effective_config(config, role).primary for role in config.roles}}
            elif args.command == "phase2-run":
                result = workflow.start(args.run_id, "修复 /hello 的缺失、空串和空白参数错误，保留合法参数行为。")
            elif args.command == "phase2-confirm":
                result = workflow.confirm_g1(args.run_id, args.principal_id)
            elif args.command == "phase2-resume":
                from .core.contracts.enums import RunStatus
                run = workflow.store.get_run(args.run_id)
                workflow.rbac.require_human(args.principal_id)
                workflow.rbac.require_role(args.principal_id, "project_owner", run.project_id)
                if run.status is not RunStatus.BLOCKED:
                    raise ValueError("仅 BLOCKED Run 可以人工恢复")
                workflow.transitions.transition(args.run_id, target_status=RunStatus.RUNNING, expected_version=run.state_version)
                result = workflow.start(args.run_id, "修复 /hello 的缺失、空串和空白参数错误，保留合法参数行为。")
            else:
                result = workflow.authorize_simulation(args.run_id, args.principal_id)
            return emit(result)
        finally:
            workflow.close()
            workflow.store.close()
    with SQLiteStore(args.data_dir / "state.db") as store:
        repo = RuntimeRepository(store, ArtifactArchive(args.data_dir / "artifacts", store))
        run = store.get_run(args.run_id)
        rbac = RBACService(store)
        skills = SkillRegistry(repo, rbac, trusted_hosts=args.trusted_host)
        mcp = MCPRegistry(repo, rbac)
        try:
            command = args.command
            if command == "phase2-status":
                rbac.assert_project_access(args.principal_id, run.project_id)
                result = {"run": run.model_dump(mode="json"), "budget": BudgetLedger(repo).summary(args.run_id),
                          "configurations": [x for x in store.runtime_list("config") if x["run_id"] == args.run_id],
                          "tool_approvals": [x for x in store.runtime_list("tool_approval") if x["run_id"] == args.run_id]}
            elif command == "phase2-export":
                result = {"run": run.model_dump(mode="json"), "budget": BudgetLedger(repo).summary(args.run_id),
                    "artifacts": [{"metadata": a.model_dump(mode="json"), "body": repo.archive.read(a.artifact_id, run_id=args.run_id)}
                                  for a in store.artifacts_for(args.run_id)],
                    "events": [e.model_dump(mode="json") for e in store.events_for(args.run_id)]}
                args.output.parent.mkdir(parents=True, exist_ok=True)
                args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                result = {"output": str(args.output.resolve())}
            elif command == "phase2-budget-approve":
                BudgetLedger(repo).approve_increase(args.request_id, principal_id=args.principal_id, rbac=rbac,
                    tokens=args.tokens, cost=args.cost, role_tokens=args.role_tokens, role_cost=args.role_cost)
                result = {"approved": args.request_id}
            elif command == "phase2-skill-import":
                result = skills.import_directory(args.run_id, args.path) if args.path.is_dir() else skills.import_archive(args.run_id, args.path)
            elif command == "phase2-skill-download":
                result = skills.download(args.run_id, args.url, args.sha256)
            elif command == "phase2-skill-git":
                result = skills.import_git(args.run_id, args.url, args.revision, principal_id=args.principal_id)
            elif command == "phase2-skill-approve":
                skills.approve(args.version, principal_id=args.principal_id, project_id=run.project_id, accepted_risks=args.accepted_risk)
                result = {"approved": args.version}
            elif command == "phase2-skill-bind":
                skills.bind(args.version, principal_id=args.principal_id, project_id=run.project_id, role=args.role)
                result = {"bound": args.version, "role": args.role}
            elif command == "phase2-skill-list":
                result = skills.list()
            elif command in {"phase2-skill-disable", "phase2-skill-uninstall"}:
                skills.set_status(args.version, "DISABLED" if command.endswith("disable") else "UNINSTALLED", principal_id=args.principal_id, project_id=run.project_id)
                result = {"updated": args.version}
            elif command == "phase2-skill-export":
                skills.export(args.version, args.output)
                result = {"output": str(args.output.resolve())}
            elif command == "phase2-skill-diff":
                result = skills.compare(args.previous_version, args.version)
            elif command == "phase2-mcp-register":
                result = {"hash": mcp.register(args.run_id, ServerConfig.model_validate_json(args.path.read_text(encoding="utf-8")))}
            elif command == "phase2-mcp-approve":
                mcp.approve(args.version, args.principal_id)
                result = {"approved": args.version}
            elif command == "phase2-mcp-test":
                result = {"tools": mcp.start(args.version).list_tools()}
            elif command in {"phase2-mcp-disable", "phase2-mcp-uninstall"}:
                mcp.disable(args.version, args.principal_id, uninstall=command.endswith("uninstall"))
                result = {"updated": args.version}
            elif command == "phase2-mcp-list":
                result = store.runtime_list("mcp_version")
            elif command == "phase2-mcp-call-approve":
                mcp.approve_call(args.request_id, args.principal_id)
                result = {"approved": args.request_id}
            else:
                if not args.idempotency_key:
                    parser.error("MCP 调用必须提供 --idempotency-key")
                config = repo.load_snapshot(args.run_id, args.role)
                result = mcp.call(run_id=args.run_id, config=config, server_id=args.server, tool_name=args.tool,
                    arguments=json.loads(args.arguments), idempotency_key=args.idempotency_key)
            emit(result)
        finally:
            mcp.close()
