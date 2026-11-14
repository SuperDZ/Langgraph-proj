"""Phase 4 本地控制台：复盘触发、报告查看、记忆提案审查与撤销。

示例身份仅供本地验收；真实项目需受信身份接入。复盘只能由有权用户显式触发。
"""
import argparse
import json
from datetime import timedelta
from pathlib import Path

from .core.approvals import RBACService
from .core.contracts.enums import ApprovalDecision, MemoryScopeType, PrincipalType
from .core.contracts.models import utc_now
from .core.orchestration import SQLiteStore
from .examples.scripted import ScriptedCurator
from .knowledge import ArtifactArchive, MemoryGovernanceService, RetrospectiveService


def open_services(data_dir):
    data_dir = Path(data_dir).resolve()
    data_dir.mkdir(parents=True, exist_ok=True)
    store = SQLiteStore(data_dir / "state.db")
    try:
        archive = ArtifactArchive(data_dir / "artifacts", store)
        rbac = RBACService(store)
        memory = MemoryGovernanceService(store, rbac)
        retro = RetrospectiveService(store, archive, rbac, memory)
        return store, archive, rbac, memory, retro
    except BaseException:
        store.close()
        raise


def ensure_demo_identities(rbac, project):
    try:
        rbac.get_principal("demo-owner")
    except KeyError:
        rbac.register_principal("demo-owner", PrincipalType.HUMAN_USER, "demo://fake-human")
    for role in ("project_owner", "memory_reviewer"):
        if role not in rbac.roles_of("demo-owner", project):
            rbac.bind_role(principal_id="demo-owner", role_id=role, scope_type="project",
                           scope_id=project, valid_from=utc_now() - timedelta(seconds=1))


def main(argv=None):
    parser = argparse.ArgumentParser(description="Phase 4 复盘与长期记忆治理（本地演示身份）")
    parser.add_argument("command", choices=[
        "phase4-retrospect", "phase4-report", "phase4-retrospectives",
        "phase4-proposals", "phase4-review", "phase4-evolve",
        "phase4-revoke", "phase4-memory"])
    parser.add_argument("--data-dir", type=Path, default=Path(".agentloop"))
    parser.add_argument("--run-id", default="demo-run")
    parser.add_argument("--retro-run-id")
    parser.add_argument("--principal-id", default="demo-owner")
    parser.add_argument("--anomaly", action="store_true", help="对已终止 Run 显式选择异常复盘")
    parser.add_argument("--redo", action="store_true", help="同版本强制重做复盘，生成新版本")
    parser.add_argument("--proposal-id")
    parser.add_argument("--decision", choices=["APPROVE", "REJECT"])
    parser.add_argument("--reason", default="")
    parser.add_argument("--verification", default="", help="演进提案批准必须附带的验证结果")
    parser.add_argument("--memory-id")
    parser.add_argument("--scope", choices=[s.value for s in MemoryScopeType])
    parser.add_argument("--scope-id", default="")
    parser.add_argument("--query", default="")
    args = parser.parse_args(argv)

    def emit(value):
        print(json.dumps(value, ensure_ascii=True, indent=2, default=str))

    store = None
    try:
        store, archive, rbac, memory, retro = open_services(args.data_dir)
        if args.command == "phase4-retrospect":
            project = store.get_run(args.run_id).project_id
            ensure_demo_identities(rbac, project)
            result = retro.trigger(run_id=args.run_id, principal_id=args.principal_id,
                                   curator=ScriptedCurator(), anomaly=args.anomaly,
                                   force_new=args.redo)
            emit(result)
        elif args.command == "phase4-report":
            retro_run = args.retro_run_id
            if not retro_run:
                records = retro.retrospectives_for(args.run_id)
                if not records:
                    raise ValueError("该 Run 尚无复盘记录")
                retro_run = records[-1]["retrospective_run_id"]
            emit(retro.report(retrospective_run_id=retro_run))
        elif args.command == "phase4-retrospectives":
            emit({"run_id": args.run_id, "retrospectives": retro.retrospectives_for(args.run_id)})
        elif args.command == "phase4-proposals":
            project = store.get_run(args.run_id).project_id
            ensure_demo_identities(rbac, project)
            # 提案挂在复盘子 Run 名下；按父 Run 汇总其全部复盘的待审队列
            child_ids = [r["retrospective_run_id"] for r in retro.retrospectives_for(args.run_id)]
            pending_memory = []
            for child in child_ids:
                pending_memory.extend(memory.pending_review(principal_id=args.principal_id, run_id=child))
            evolutions = []
            for child in child_ids:
                evolutions.extend(store.evolution_proposals_for(child))
            emit({"memory_proposals": [p.model_dump(mode="json") for p in pending_memory],
                  "evolution_proposals": [e.model_dump(mode="json") for e in evolutions]})
        elif args.command == "phase4-review":
            if not args.proposal_id or not args.decision:
                raise ValueError("需要 --proposal-id 与 --decision")
            proposal = store.get_memory_proposal(args.proposal_id)
            project = store.get_run(proposal.run_id).project_id
            ensure_demo_identities(rbac, project)
            decided = memory.decide_memory(proposal_id=args.proposal_id,
                                           decision=ApprovalDecision(args.decision),
                                           principal_id=args.principal_id, reason=args.reason)
            emit(decided.model_dump(mode="json"))
        elif args.command == "phase4-evolve":
            if not args.proposal_id or not args.decision:
                raise ValueError("需要 --proposal-id 与 --decision")
            proposal = store.get_evolution_proposal(args.proposal_id)
            project = store.get_run(proposal.run_id).project_id
            ensure_demo_identities(rbac, project)
            decided = memory.decide_evolution(proposal_id=args.proposal_id,
                                              decision=ApprovalDecision(args.decision),
                                              principal_id=args.principal_id,
                                              verification_result=args.verification, reason=args.reason)
            emit(decided.model_dump(mode="json"))
        elif args.command == "phase4-revoke":
            if not args.memory_id:
                raise ValueError("需要 --memory-id")
            record = store.get_memory(args.memory_id)
            project = store.get_run(record.origin_run_id).project_id
            ensure_demo_identities(rbac, project)
            emit(memory.revoke_memory(memory_id=args.memory_id, principal_id=args.principal_id,
                                      reason=args.reason or "manual revoke").model_dump(mode="json"))
        elif args.command == "phase4-memory":
            if not args.principal_id:
                raise ValueError("需要 --principal-id")
            project = store.get_run(args.run_id).project_id
            ensure_demo_identities(rbac, project)
            records = memory.search(principal_id=args.principal_id,
                                    scope_type=MemoryScopeType(args.scope) if args.scope else None,
                                    scope_id=args.scope_id or None,
                                    project_id=project, query=args.query or None)
            emit({"count": len(records), "memories": [r.model_dump(mode="json") for r in records]})
        return 0
    finally:
        if store is not None:
            store.close()
