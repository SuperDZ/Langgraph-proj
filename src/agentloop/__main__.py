"""Phase 0 离线演示。demo 身份仅用于本地假环境，不是真实认证。"""

import argparse
import json
from datetime import timedelta
from pathlib import Path

from .core.approvals import RBACService
from .core.contracts.enums import PrincipalType, RunStatus, RunType
from .core.contracts.models import utc_now
from .core.orchestration import SQLiteStore, StateTransitionService
from .core.orchestration.clarifications import ClarificationService
from .core.orchestration.intake_graph import IntakeGraph


def main():
    import sys
    if len(sys.argv)>1 and sys.argv[1].startswith("phase3-"):
        from .phase3_cli import main as phase3_main
        from .core.approvals.rbac import AccessDenied
        from .core.orchestration import TransitionRejected
        from pydantic import ValidationError
        try:
            return phase3_main(sys.argv[1:])
        except ValidationError as exc:
            print(json.dumps({"error":"CONFIG_VALIDATION_FAILED","paths":[list(e["loc"]) for e in exc.errors(include_input=False)]}))
            raise SystemExit(2) from None
        except (ValueError,PermissionError,AccessDenied,TransitionRejected) as exc:
            print(json.dumps({"error":str(exc)},ensure_ascii=True));raise SystemExit(2) from None
    if len(sys.argv) > 1 and sys.argv[1].startswith("phase2-"):
        from .runtime_cli import main as phase2_main
        from pydantic import ValidationError
        from .core.approvals.rbac import AccessDenied
        try:
            return phase2_main(sys.argv[1:])
        except ValidationError as exc:
            # 不回显可能含密钥的非法输入，仅返回字段路径。
            print(json.dumps({"error": "CONFIG_VALIDATION_FAILED", "paths": [list(e["loc"]) for e in exc.errors(include_input=False)]}))
            raise SystemExit(2) from None
        except (ValueError, PermissionError, AccessDenied) as exc:
            print(json.dumps({"error": str(exc)}, ensure_ascii=True))
            raise SystemExit(2) from None
    parser = argparse.ArgumentParser(description="Phase 0 本地假身份/假任务演示，不调用模型或远端服务")
    parser.add_argument("command", choices=["demo-start", "demo-answer", "demo-status", "phase1-run", "phase1-confirm", "phase1-authorize", "phase1-status", "phase1-export"])
    parser.add_argument("--data-dir", type=Path, default=Path(".agentloop/demo"))
    parser.add_argument("--run-id", default="demo-run")
    parser.add_argument("--answer")
    parser.add_argument("--java-home")
    parser.add_argument("--maven")
    parser.add_argument("--require-confirmation", action="store_true")
    parser.add_argument("--security-example", action="store_true", help="演示确定性安全扫描阻断与研发整改")
    parser.add_argument("--output", type=Path, default=Path("docs/phase1-delivery-evidence.json"))
    args = parser.parse_args()
    if args.command.startswith("phase1-"):
        from .examples.demo import build_demo
        workflow = build_demo(data_dir=args.data_dir, run_id=args.run_id, java_home=args.java_home,
            maven=args.maven, require_confirmation=args.require_confirmation, security_example=args.security_example)
        try:
            if args.command == "phase1-run":
                result = workflow.start(args.run_id, "修复 /hello 的缺失、空串和空白参数错误，保留合法参数行为。")
            elif args.command == "phase1-confirm":
                result = workflow.confirm_g1(args.run_id, "demo-owner")
            elif args.command == "phase1-authorize":
                result = workflow.authorize_simulation(args.run_id, "demo-owner")
            elif args.command == "phase1-export":
                artifacts = workflow.store.artifacts_for(args.run_id)
                result = {"summary": workflow.summary(args.run_id),
                    "evidence_boundary": "Scripted role outputs; actual Maven/Spring HTTP assertions; fake human demo identity; local simulated deployment only.",
                    "artifacts": [{"metadata": a.model_dump(mode="json"), "body": workflow.archive.read(a.artifact_id, run_id=args.run_id)} for a in artifacts],
                    "events": [e.model_dump(mode="json") for e in workflow.store.events_for(args.run_id)]}
                args.output.parent.mkdir(parents=True, exist_ok=True)
                args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
                result = {"output": str(args.output.resolve()), "artifact_count": len(artifacts)}
            else:
                result = workflow.summary(args.run_id)
            print(json.dumps(result, ensure_ascii=True, indent=2))
        finally:
            workflow.close()
            workflow.store.close()
        return
    args.data_dir.mkdir(parents=True, exist_ok=True)
    with SQLiteStore(args.data_dir / "state.db") as store:
        transitions, rbac = StateTransitionService(store), RBACService(store)
        if args.command == "demo-start":
            rbac.register_principal("demo-owner", PrincipalType.HUMAN_USER, "demo://fake-identity")
            if not rbac.roles_of("demo-owner", "demo-project"):
                rbac.bind_role(principal_id="demo-owner", role_id="project_owner", scope_type="project",
                    scope_id="demo-project", valid_from=utc_now() - timedelta(seconds=1))
            if store.find_run(args.run_id) is None:
                transitions.create_run(run_id=args.run_id, run_type=RunType.DELIVERY,
                    project_id="demo-project", trigger_source="USER", config_snapshot_id="demo-config")
                transitions.transition(args.run_id, target_status=RunStatus.RUNNING)
        clarifications = ClarificationService(store, transitions, rbac)
        graph = IntakeGraph(args.data_dir / "checkpoints.db", clarifications)
        try:
            if args.command == "demo-start":
                graph.start(args.run_id, "请提供接口 Bug 的复现参数与期望结果。")
            elif args.command == "demo-answer":
                if not args.answer:
                    parser.error("demo-answer 必须提供 --answer")
                questions = store.clarifications_for(args.run_id)
                if not questions:
                    parser.error("该 Run 没有澄清请求，请先运行 demo-start")
                graph.resume(run_id=args.run_id, question_id=questions[-1].question_id,
                    principal_id="demo-owner", answer=args.answer,
                    expected_version=store.get_run(args.run_id).state_version)
            run = store.get_run(args.run_id)
            snapshot = graph.graph.get_state(graph.config(args.run_id))
            print(json.dumps({"mode": "OFFLINE_DEMO", "run_id": run.run_id,
                "thread_id": run.run_id, "phase": run.phase.value, "status": run.status.value,
                "state_version": run.state_version, "checkpoint_next": list(snapshot.next),
                "questions": [q.model_dump(mode="json") for q in store.clarifications_for(run.run_id)],
                "event_count": len(store.events_for(run.run_id))}, ensure_ascii=True, indent=2))
        finally:
            graph.close()


if __name__ == "__main__":
    main()
