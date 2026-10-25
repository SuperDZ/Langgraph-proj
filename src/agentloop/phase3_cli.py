"""Phase 3 本地控制台。示例身份仅供本地验收，真实项目需受信身份接入。"""
import argparse
import json
import ssl
import time
from datetime import timedelta
from pathlib import Path
from .core.approvals import RBACService
from .core.approvals.releases import ReleaseService
from .core.contracts.enums import PrincipalType,ApprovalDecision,ReleaseAction,RunPhase,RunStatus
from .core.contracts.models import utc_now
from .core.contracts.phase3 import DeploymentTarget,ExecutionPolicy
from .core.orchestration import SQLiteStore
from .core.runtime.configuration import RuntimeRepository
from .core.runtime.deployment_providers import LocalStaticProvider,HTTPDeploymentProvider
from .core.runtime.effects import SideEffectExecutor
from .core.runtime.operations import DeploymentCoordinator,CancellationService,MaintenanceService
from .knowledge.archive import ArtifactArchive


def local_identities(rbac,project):
    for principal,kind,roles in [("phase3-executor",PrincipalType.SYSTEM_SERVICE,["side_effect_executor"]),
        ("operations-expert",PrincipalType.AGENT_SERVICE,["viewer"]),
        ("demo-security",PrincipalType.HUMAN_USER,["security_reviewer"])]:
        rbac.register_principal(principal,kind,"demo://"+principal)
        for role in roles:
            if role not in rbac.roles_of(principal,project):
                rbac.bind_role(principal_id=principal,role_id=role,scope_type="project",scope_id=project,valid_from=utc_now()-timedelta(seconds=1))
    if "operator" not in rbac.roles_of("demo-owner",project):
        rbac.bind_role(principal_id="demo-owner",role_id="operator",scope_type="project",scope_id=project,valid_from=utc_now()-timedelta(seconds=1))


def main(argv=None):
    parser=argparse.ArgumentParser(description="Phase 3 受控开发、授权发布、恢复和巡检")
    parser.add_argument("command",choices=["phase3-run","phase3-confirm","phase3-status","phase3-target","phase3-request",
        "phase3-approve","phase3-reject","phase3-revoke","phase3-deploy","phase3-reconcile","phase3-remediate",
        "phase3-terminate","phase3-cancel","phase3-settle-cancel","phase3-schedule","phase3-tick","phase3-watch","phase3-export","phase3-agent","phase3-rework","phase3-config","phase3-rollback",
        "phase3-waiver-request","phase3-waiver-approve","phase3-waiver-reject","phase3-waiver-revoke"])
    parser.add_argument("--data-dir",type=Path,default=Path(".agentloop/phase3"))
    parser.add_argument("--run-id",default="phase3-run")
    parser.add_argument("--java-home");parser.add_argument("--maven")
    parser.add_argument("--require-confirmation",action="store_true")
    parser.add_argument("--principal-id",default="demo-owner")
    parser.add_argument("--actor-id",default="operations-expert")
    parser.add_argument("--target-file",type=Path);parser.add_argument("--target-id",default="local-staging")
    parser.add_argument("--runtime-config",type=Path)
    parser.add_argument("--authorization-id");parser.add_argument("--request-id");parser.add_argument("--deployment-id");parser.add_argument("--effect-id")
    parser.add_argument("--rollback-only",action="store_true")
    parser.add_argument("--waiver-id");parser.add_argument("--issue-id",action="append",default=[])
    parser.add_argument("--rationale",default="");parser.add_argument("--controls",default="");parser.add_argument("--hours",type=float,default=24)
    parser.add_argument("--cause",choices=["ENV_DEFECT","CODE_DEFECT","SPEC_DEFECT","ARCH_DEFECT"])
    parser.add_argument("--idempotency-key",default="deployment-1")
    parser.add_argument("--interval",type=int,default=300)
    parser.add_argument("--output",type=Path,default=Path("docs/phase3-delivery-evidence.json"))
    parser.add_argument("--port",type=int,default=8766);parser.add_argument("--host",default="127.0.0.1")
    parser.add_argument("--token-ref",default="env:AGENTLOOP_DEPLOY_AGENT_TOKEN")
    parser.add_argument("--cert-file");parser.add_argument("--key-file")
    parser.add_argument("--enable-production",action="store_true")
    args=parser.parse_args(argv)
    def emit(value): print(json.dumps(value,ensure_ascii=True,indent=2,default=str))
    if args.command=="phase3-config":
        from .runtime_cli import default_config
        config=default_config()
        config["roles"].update({"frontend":{"department":"engineering"},"devops":{"department":"engineering"}})
        args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(config,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
        return emit({"output":str(args.output.resolve())})
    if args.command=="phase3-agent":
        if not args.target_file: parser.error("phase3-agent 需要 --target-file")
        target=DeploymentTarget.model_validate_json(args.target_file.read_text(encoding="utf-8"))
        if args.host not in {"127.0.0.1","localhost","::1"} and not (args.cert_file and args.key_file):
            parser.error("非回环监听必须配置 TLS 证书和私钥")
        if target.environment=="production" and not (args.cert_file and args.key_file): parser.error("production 代理必须启用 TLS")
        from .deployment_agent import create_agent_server
        server,provider=create_agent_server(target,args.data_dir/"agent-target",host=args.host,port=args.port,token_ref=args.token_ref)
        if args.cert_file and args.key_file:
            context=ssl.SSLContext(ssl.PROTOCOL_TLS_SERVER);context.load_cert_chain(args.cert_file,args.key_file)
            server.socket=context.wrap_socket(server.socket,server_side=True)
        emit({"agent":"READY","target":target.target_id,"port":server.server_port,"environment":target.environment,
              "application_url":f"http://127.0.0.1:{provider.server.server_port}/"})
        try:server.serve_forever()
        except KeyboardInterrupt:pass
        finally:server.server_close();provider.close()
        return
    if args.command in {"phase3-run","phase3-confirm","phase3-rework"}:
        from .examples.demo import build_demo
        from .core.contracts.phase2 import RuntimeConfig
        runtime=RuntimeConfig.model_validate_json(args.runtime_config.read_text(encoding="utf-8")) if args.runtime_config else None
        workflow=build_demo(data_dir=args.data_dir,run_id=args.run_id,java_home=args.java_home,maven=args.maven,
                            require_confirmation=args.require_confirmation,phase3=True,runtime_config=runtime)
        try:
            local_identities(workflow.rbac,workflow.config.project_id)
            if args.command=="phase3-run":
                result=workflow.start(args.run_id,"多角色修复 hello 参数边界，交付页面和部署配置。")
            elif args.command=="phase3-rework":
                workflow.rbac.require_human(args.principal_id);workflow.rbac.require_role(args.principal_id,"project_owner",workflow.config.project_id)
                result=workflow.resume_rework(args.run_id)
            else:result=workflow.confirm_g1(args.run_id,args.principal_id)
            emit(result)
        finally:workflow.close();workflow.store.close()
        return
    args.data_dir.mkdir(parents=True,exist_ok=True)
    with SQLiteStore(args.data_dir/"state.db") as store:
        run=store.get_run(args.run_id);rbac=RBACService(store)
        rbac.assert_project_access(args.principal_id,run.project_id)
        repo=RuntimeRepository(store,ArtifactArchive(args.data_dir/"artifacts",store))
        executor=SideEffectExecutor(repo,service_principal="phase3-executor",providers={},production_enabled=args.enable_production)
        coordinator=DeploymentCoordinator(executor);releases=ReleaseService(store,executor.transitions,rbac)
        providers={}
        def connect(target_id):
            if target_id not in providers:
                target,_=executor.target(run.project_id,target_id)
                providers[target_id]=LocalStaticProvider(args.data_dir/"targets"/target_id,target) if target.provider=="local-static" else HTTPDeploymentProvider(target)
                executor.providers[target_id]=providers[target_id]
            return providers[target_id]
        try:
            command=args.command
            if command=="phase3-target":
                target=DeploymentTarget.model_validate_json(args.target_file.read_text(encoding="utf-8")) if args.target_file else DeploymentTarget(target_id=args.target_id,project_id=run.project_id,environment="staging",provider="http-agent",endpoint=f"http://127.0.0.1:{args.port}",secret_ref=args.token_ref)
                executor.register_target(target,principal_id=args.principal_id)
                from urllib.parse import urlparse
                caps=["cap.deploy.staging","cap.deploy.production"]
                policy=ExecutionPolicy(principal_id=args.actor_id,role="operations-expert",platform=caps,department=caps,agent=caps,task=caps,target_ids=[target.target_id],
                    network_hosts=[urlparse(target.endpoint).hostname] if target.endpoint else [],secrets=[target.secret_ref] if target.secret_ref else [])
                executor.bind_policy(run.run_id,policy,principal_id=args.principal_id)
                result={"target":target.model_dump(mode="json"),"authorization_required":True}
            elif command=="phase3-request":
                release=store.releases_for(run.run_id)[-1]
                target,_=executor.target(run.project_id,args.target_id)
                if target.provider=="local-static":raise ValueError("CLI 常驻发布需独立 HTTP 代理；local-static 仅用于同进程集成验证")
                result=releases.request(release_id=release.release_id,principal_id=args.principal_id,environment_id=target.environment,
                    target_ids=[args.target_id],action_scope=[ReleaseAction.ROLLBACK] if args.rollback_only else [ReleaseAction.DEPLOY,ReleaseAction.ROLLBACK]).model_dump(mode="json")
            elif command in {"phase3-approve","phase3-reject"}:
                authorization=releases.decide(request_id=args.request_id,principal_id=args.principal_id,
                    decision=ApprovalDecision.APPROVE if command.endswith("approve") else ApprovalDecision.REJECT)
                result=authorization.model_dump(mode="json") if authorization else {"rejected":args.request_id}
            elif command=="phase3-revoke":
                releases.revoke(args.authorization_id,args.principal_id);result={"revoked":args.authorization_id}
            elif command=="phase3-deploy":
                rbac.require_human(args.principal_id);rbac.require_role(args.principal_id,"operator",run.project_id)
                authorization=store.get_authorization(args.authorization_id)
                target,_=executor.target(run.project_id,args.target_id)
                if target.environment=="production" and rbac.get_principal(authorization.issued_by).identity_provider_ref.startswith("demo://"):
                    raise PermissionError("演示身份不能授权真实生产发布")
                from .core.runtime.configuration import digest
                effect=store.runtime_get("effect",digest({"run":run.run_id,"key":args.idempotency_key}))
                if not effect:
                    executor._validate(run.run_id,args.actor_id,args.authorization_id,args.target_id)
                    connect(args.target_id)
                saved=store.runtime_get("release_bundle",authorization.release_id)
                if not saved:raise ValueError("缺少可信发布包")
                bundle=repo.archive.read(saved["artifact_id"],run_id=run.run_id)
                deployment=executor.execute(run_id=run.run_id,actor_id=args.actor_id,authorization_id=args.authorization_id,
                    target_id=args.target_id,bundle=bundle,idempotency_key=args.idempotency_key)
                result=coordinator.finalize(deployment.deployment_id,actor_id=args.actor_id).model_dump(mode="json")
                if result["status"]=="COMPLETED":
                    from .examples.demo import build_demo
                    class NoExecution:
                        def run(self,*args,**kwargs):raise ValueError("只同步交付 checkpoint，不执行测试")
                    workflow=build_demo(data_dir=args.data_dir,run_id=run.run_id,phase3=True,runner=NoExecution(),checkpoint_only=True)
                    try:workflow.sync_delivery_checkpoint(run.run_id,deployment.deployment_id)
                    finally:workflow.close();workflow.store.close()
            elif command=="phase3-reconcile":
                effect=store.runtime_get("effect",args.effect_id);connect(effect["target_id"])
                deployment=executor.reconcile(args.effect_id,principal_id=args.principal_id)
                result=coordinator.recover(deployment.deployment_id,actor_id=args.actor_id).model_dump(mode="json")
            elif command=="phase3-rollback":
                rbac.require_human(args.principal_id);rbac.require_role(args.principal_id,"operator",run.project_id)
                deployment=store.get_deployment(args.deployment_id);connect(deployment.target_ids[0])
                executor.rollback(deployment.deployment_id,actor_id=args.actor_id,authorization_id=args.authorization_id)
                result=coordinator.recover(deployment.deployment_id,actor_id=args.actor_id).model_dump(mode="json")
            elif command in {"phase3-remediate","phase3-terminate"}:
                deployment=store.get_deployment(args.deployment_id);connect(deployment.target_ids[0])
                result=(coordinator.remediate(deployment.deployment_id,cause=args.cause,principal_id=args.principal_id) if command.endswith("remediate")
                    else coordinator.terminate(deployment.deployment_id,principal_id=args.principal_id)).model_dump(mode="json")
            elif command=="phase3-cancel":result=CancellationService(coordinator).request(run.run_id,principal_id=args.principal_id).model_dump(mode="json")
            elif command=="phase3-settle-cancel":
                for deployment in store.deployments_for(run.run_id):connect(deployment.target_ids[0])
                result=CancellationService(coordinator).settle(run.run_id,principal_id=args.principal_id,actor_id=args.actor_id).model_dump(mode="json")
            elif command in {"phase3-schedule","phase3-tick","phase3-watch"}:
                service=MaintenanceService(executor)
                if command=="phase3-schedule":result=service.schedule(run.run_id,args.target_id,principal_id=args.principal_id,interval_seconds=args.interval)
                else:
                    for schedule in store.runtime_list("maintenance_schedule"):
                        if schedule["parent"]==run.run_id:connect(schedule["target"])
                    if command=="phase3-tick": result=[r.model_dump(mode="json") for r in service.tick(parent_run_id=run.run_id)]
                    else:
                        try:
                            while True:
                                children=service.tick(parent_run_id=run.run_id)
                                if children:emit([r.model_dump(mode="json") for r in children])
                                time.sleep(1)
                        except KeyboardInterrupt:return
            elif command=="phase3-export":
                body={"run":run.model_dump(mode="json"),"artifacts":[{"metadata":a.model_dump(mode="json"),"body":repo.archive.read(a.artifact_id,run_id=run.run_id)} for a in store.artifacts_for(run.run_id)],
                    "events":[e.model_dump(mode="json") for e in store.events_for(run.run_id)]}
                args.output.parent.mkdir(parents=True,exist_ok=True);args.output.write_text(json.dumps(body,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
                result={"output":str(args.output.resolve())}
            elif command.startswith("phase3-waiver-"):
                from .core.approvals.waivers import RiskWaiverService
                service=RiskWaiverService(repo,rbac,executor.transitions)
                if command=="phase3-waiver-request":
                    result=service.request(run.run_id,principal_id=args.principal_id,issue_ids=args.issue_id,rationale=args.rationale,controls=args.controls,hours=args.hours).model_dump(mode="json")
                elif command=="phase3-waiver-revoke":
                    service.revoke(args.waiver_id,principal_id=args.principal_id);result={"revoked":args.waiver_id}
                else:result=service.decide(args.waiver_id,principal_id=args.principal_id,approve=command.endswith("approve")).model_dump(mode="json")
            else:
                result={"run":run.model_dump(mode="json"),"deployments":[d.model_dump(mode="json") for d in store.deployments_for(run.run_id)],
                    "effects":[e for e in store.runtime_list("effect") if e["run_id"]==run.run_id],"releases":[r.model_dump(mode="json") for r in store.releases_for(run.run_id)],
                    "children":[r.model_dump(mode="json") for r in store.list_runs(run.project_id) if r.parent_run_id==run.run_id]}
            emit(result)
        finally:
            for provider in providers.values():provider.close()
