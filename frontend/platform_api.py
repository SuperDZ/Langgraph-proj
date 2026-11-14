"""Local-only Phase 4/5 API. Identity is fixed by the host, never by request JSON."""
from contextlib import contextmanager
from pathlib import Path
import json
from agentloop.core.orchestration import SQLiteStore
from agentloop.core.approvals import RBACService
from agentloop.core.contracts.enums import ApprovalDecision
from agentloop.knowledge import ArtifactArchive, MemoryGovernanceService, RetrospectiveService
from agentloop.core.runtime.configuration import RuntimeRepository, effective_config
from agentloop.core.runtime.skills import SkillRegistry
from agentloop.core.runtime.budget import BudgetLedger
from agentloop.core.contracts.phase2 import RuntimeConfig
from agentloop.examples.scripted import ScriptedCurator
from agentloop.runtime_cli import default_config


def dump(value):
    return value.model_dump(mode='json')


class Platform:
    def __init__(self, bench):
        self.bench = bench
        self.root = bench.data_dir / 'runs'
        self.root.mkdir(parents=True, exist_ok=True)
        self.principal = 'demo-owner'
        from agentloop.core.contracts.enums import PrincipalType
        from agentloop.core.contracts.models import utc_now
        from datetime import timedelta
        project = json.loads((Path(__file__).parents[1]/'src/agentloop/examples/phase1-config.json').read_text())['project_id']
        with SQLiteStore(self.root/'state.db') as store:
            rbac=RBACService(store)
            try: store.get_principal(self.principal)
            except KeyError: rbac.register_principal(self.principal,PrincipalType.HUMAN_USER,'demo://fake-human')
            for role in ('project_owner','release_approver','memory_reviewer'):
                if role not in rbac.roles_of(self.principal,project):
                    rbac.bind_role(principal_id=self.principal,role_id=role,scope_type='project',scope_id=project,valid_from=utc_now()-timedelta(seconds=1))
            for role in self.default_config()['roles']:
                try: store.get_principal(role)
                except KeyError: rbac.register_principal(role,PrincipalType.AGENT_SERVICE,'demo://'+role)
                if 'viewer' not in rbac.roles_of(role,project):
                    rbac.bind_role(principal_id=role,role_id='viewer',scope_type='project',scope_id=project,valid_from=utc_now()-timedelta(seconds=1))

    @contextmanager
    def services(self):
        with SQLiteStore(self.root / 'state.db') as store:
            archive = ArtifactArchive(self.root / 'artifacts', store)
            rbac = RBACService(store)
            memory = MemoryGovernanceService(store, rbac)
            yield store, archive, rbac, memory, RetrospectiveService(store, archive, rbac, memory)

    def access(self, store, rbac, run_id):
        run = store.get_run(run_id)
        rbac.assert_project_access(self.principal, run.project_id)
        return run

    def read(self, run_id=None):
        with self.services() as (store, archive, rbac, memory, retro):
            runs = []
            for run in store.list_runs():
                try:
                    self.access(store, rbac, run.run_id)
                except Exception:
                    continue
                runs.append(dump(run))
            config = store.runtime_get('console_config', 'draft') or self.default_config()
            result = {'runs': runs, 'config': config, 'identity': self.principal,
                      'boundary': '本机演示身份；脚本角色、真实本地测试；生产发布禁用。'}
            result['credentials'] = self.bench.credentials.status(self.model_secret_refs(config))
            validated = RuntimeConfig.model_validate(config)
            result['config'] = validated.model_dump(mode='json')
            result['effective_agents'] = {role: effective_config(validated,role).model_dump(mode='json') for role in validated.roles}
            if not run_id or store.find_run(run_id) is None:
                return result
            run = self.access(store, rbac, run_id)
            records = retro.retrospectives_for(run_id)
            child_ids = {r['retrospective_run_id'] for r in records}
            visible = [m for m in store.memories() if store.get_run(m.origin_run_id).project_id == run.project_id]
            result.update(run=dump(run), events=[dump(e) for e in store.events_for(run_id)],
                gates=[dump(g) for g in store.gate_results_for(run_id)],
                artifacts=[{'metadata': dump(a), 'body': archive.read(a.artifact_id, run_id=run_id)} for a in store.artifacts_for(run_id)],
                clarifications=[dump(c) for c in store.clarifications_for(run_id)],
                approvals=[dump(a) for a in store.approval_requests_for(run_id)],
                releases=[dump(r) for r in store.releases_for(run_id)],
                deployments=[dump(d) for d in store.deployments_for(run_id)],
                authorization_requests=[dump(a) for a in store.authorization_requests_for(run_id)],
                authorizations=[dump(a) for a in store.authorizations_for(run_id)],
                retrospectives=records,
                proposals=[dump(p) for child in child_ids for p in memory.pending_review(principal_id=self.principal,run_id=child)],
                evolutions=[dump(p) for child in child_ids for p in store.evolution_proposals_for(child)],
                memories=list(map(dump, visible)),
                budgets=[b for b in store.runtime_list('budget') if b.get('root')==run.root_run_id],
                budget_summary=BudgetLedger(RuntimeRepository(store, archive)).summary(run_id),
                skills=SkillRegistry(RuntimeRepository(store, archive),rbac).list())
            result['skills']=[s for s in result['skills'] if store.get_run(s['source_run']).project_id==run.project_id]
            result['mcp']=[r for r in store.runtime_list('mcp_version') if r['project']==run.project_id]
            result['reports'] = [retro.report(retrospective_run_id=r['retrospective_run_id']) for r in records]
            return result

    def default_config(self):
        config = default_config()
        config['roles'].update(frontend={'department':'engineering'}, devops={'department':'engineering'})
        return config

    def act(self, action, body):
        with self.services() as (store, archive, rbac, memory, retro):
            config_actions = {'agent-config-save', 'credential-save', 'credential-remove',
                              'credential-register', 'global-config-save',
                              'model-profile-save', 'model-profile-delete'}
            if action in config_actions:
                project = json.loads((Path(__file__).parents[1]/'src/agentloop/examples/phase1-config.json').read_text())['project_id']
                rbac.require_human(self.principal)
                rbac.require_role(self.principal,'project_owner',project)
                with store.transaction():
                    current = store.runtime_get('console_config','draft') or self.default_config()
                    if action in {'credential-save', 'credential-remove'}:
                        ref = body.get('ref')
                        if ref not in self.model_secret_refs(current): raise ValueError('未登记的模型凭据引用')
                        # The vault writes encrypted bytes only; no secret enters SQLite or audit.
                        return self.bench.credentials.update(ref,body.get('value'),remove=action=='credential-remove')
                    from agent_settings import (delete_model, edit_agent, edit_global,
                        register_credential, save_model)
                    from pydantic import ValidationError
                    try:
                        if action == 'agent-config-save':
                            config, effective = edit_agent(current, body)
                        elif action == 'global-config-save':
                            config, effective = edit_global(current, body)
                        elif action == 'model-profile-save':
                            config, effective = save_model(current, body)
                        elif action == 'model-profile-delete':
                            config, effective = delete_model(current, body.get('profile_id'))
                        else:
                            config, effective = register_credential(current, body.get('ref'))
                    except ValidationError as exc:
                        raise ValueError('；'.join(e['msg'] for e in exc.errors(include_input=False,include_url=False))) from None
                    credential_status = None
                    if action == 'credential-register':
                        credential_status = self.bench.credentials.update(body['ref'], body.get('value'))
                    elif action == 'model-profile-save' and body.get('api_key'):
                        credential_status = self.bench.credentials.update(config['models'][body['profile_id']]['secret_ref'], body['api_key'])
                    store.runtime_put('console_config','draft',config)
                    result = {'saved':True,'effective':effective,'applies_to':'NEW_RUNS_ONLY'}
                    if action == 'agent-config-save': result['role'] = body['role']
                    if credential_status is not None: result['credential'] = credential_status
                    return result
            if action == 'config-save' and not store.find_run(body['run_id']):
                project = json.loads((Path(__file__).parents[1]/'src/agentloop/examples/phase1-config.json').read_text())['project_id']
                rbac.require_human(self.principal);rbac.require_role(self.principal,'project_owner',project)
                config=RuntimeConfig.model_validate(body['config'])
                for role in config.roles: effective_config(config,role)
                store.runtime_put('console_config','draft',config.model_dump(mode='json'))
                return {'saved':True,'applies_to':'NEW_RUNS_ONLY'}
            run = self.access(store, rbac, body['run_id'])
            principal = self.principal
            if action == 'evolution-publish':
                proposal=store.get_evolution_proposal(body['proposal_id'])
                if store.get_run(proposal.run_id).root_run_id!=run.root_run_id: raise PermissionError('提案不属于所选运行')
                return memory.publish_evolution(proposal_id=proposal.proposal_id,skill_hash=body['hash'],role=body['role'],verification_artifact_id=body['verification_artifact_id'],principal_id=principal,archive=archive)
            if action == 'skill-import':
                rbac.require_human(principal);rbac.require_role(principal,'project_owner',run.project_id)
                import base64,tempfile
                content=base64.b64decode(body['content'],validate=True)
                if len(content)>600000: raise ValueError('上传包超过 600 KB')
                with tempfile.TemporaryDirectory() as tmp:
                    package=Path(tmp)/'upload.zip';package.write_bytes(content)
                    return SkillRegistry(RuntimeRepository(store,archive),rbac).import_archive(run.run_id,package)
            if action in {'mcp-register','mcp-approve','mcp-disable'}:
                from agentloop.core.runtime.mcp import MCPRegistry,ServerConfig
                rbac.require_human(principal);rbac.require_role(principal,'project_owner',run.project_id)
                registry=MCPRegistry(RuntimeRepository(store,archive),rbac)
                if action=='mcp-register':
                    config=ServerConfig.model_validate(body['config'])
                    if config.transport!='http': raise ValueError('Web 注册仅支持 HTTP；stdio 由受信主机 CLI 登记')
                    return {'hash':registry.register(run.run_id,config)}
                record=store.runtime_get('mcp_version',body['hash'])
                if record['project']!=run.project_id: raise PermissionError('MCP 不属于当前项目')
                if action=='mcp-approve': registry.approve(body['hash'],principal)
                else: registry.disable(body['hash'],principal)
                return {'updated':True}
            if action == 'retrospect':
                # Demo role registration is confined to the fixed local owner.
                if 'memory_reviewer' not in rbac.roles_of(principal,run.project_id):
                    rbac.require_role(principal,'project_owner',run.project_id)
                    from agentloop.core.contracts.models import utc_now
                    from datetime import timedelta
                    rbac.bind_role(principal_id=principal,role_id='memory_reviewer',scope_type='project',scope_id=run.project_id,valid_from=utc_now()-timedelta(seconds=1))
                return retro.trigger(run_id=run.run_id,principal_id=principal,curator=ScriptedCurator(),anomaly=body.get('anomaly') is True,force_new=body.get('redo') is True)
            if action in {'memory-review','evolution-review'}:
                proposal = store.get_memory_proposal(body['proposal_id']) if action=='memory-review' else store.get_evolution_proposal(body['proposal_id'])
                if store.get_run(proposal.run_id).root_run_id != run.root_run_id:
                    raise PermissionError('提案不属于所选根运行')
                method = memory.decide_memory if action=='memory-review' else memory.decide_evolution
                args = dict(proposal_id=proposal.proposal_id,decision=ApprovalDecision(body['decision']),principal_id=principal,reason=body.get('reason',''))
                if action=='evolution-review': args['verification_result']=body.get('verification','')
                return dump(method(**args))
            if action in {'memory-revoke','memory-rollback'}:
                record = store.get_memory(body['memory_id'])
                if store.get_run(record.origin_run_id).project_id != run.project_id:
                    raise PermissionError('记忆不属于当前项目')
                return dump(memory.revoke_memory(memory_id=record.memory_id,principal_id=principal,reason=body.get('reason','人工撤销')) if action=='memory-revoke' else memory.rollback_memory(memory_id=record.memory_id,principal_id=principal,reason=body.get('reason','人工回滚')))
            if action=='config-save':
                rbac.require_human(principal);rbac.require_role(principal,'project_owner',run.project_id)
                config=RuntimeConfig.model_validate(body['config'])
                for role in config.roles: effective_config(config,role)
                with store.transaction():
                    store.runtime_put('console_config','draft',config.model_dump(mode='json'))
                    RuntimeRepository(store,archive).audit(run.run_id,'CONSOLE_CONFIG_SAVED',{'principal':principal})
                return {'saved':True,'applies_to':'NEW_RUNS_ONLY'}
            if action=='skill-approve':
                registry=SkillRegistry(RuntimeRepository(store,archive),rbac)
                registry.approve(body['hash'],principal_id=principal,project_id=run.project_id,accepted_risks=body.get('risks',[]))
                registry.bind(body['hash'],principal_id=principal,project_id=run.project_id,role=body['role'])
                return {'bound':True}
            if action=='clarify':
                from agentloop.core.orchestration.clarifications import ClarificationService
                request=store.get_clarification(body['question_id'])
                if request.run_id != run.run_id: raise PermissionError('问题不属于当前运行')
                return dump(ClarificationService(store,__import__("agentloop.core.orchestration.state_transition",fromlist=["StateTransitionService"]).StateTransitionService(store),rbac).answer(question_id=request.question_id,principal_id=principal,answer=body['answer'],expected_version=body['expected_version']))
            raise ValueError('不支持的治理操作')

    @staticmethod
    def model_secret_refs(config):
        refs = {m.get('secret_ref','env:DEEPSEEK_API_KEY') for m in config['models'].values()}
        refs.update(config.get('platform',{}).get('policy',{}).get('secrets',[]))
        return refs

def release_command(bench, body):
    """Allowlisted staging CLI bridge; never interpolate a shell command."""
    import contextlib, io
    from agentloop.phase3_cli import main
    from agentloop.phase3_cli import local_identities
    with SQLiteStore(bench.data_dir/'runs/state.db') as store:
        run=store.get_run(body['run_id'])
        local_identities(RBACService(store),run.project_id)
    command=body.get('command')
    mapping={'target':'phase3-target','request':'phase3-request','approve':'phase3-approve','reject':'phase3-reject','deploy':'phase3-deploy','reconcile':'phase3-reconcile','rollback':'phase3-rollback','schedule':'phase3-schedule','tick':'phase3-tick','cancel':'phase3-cancel','settle-cancel':'phase3-settle-cancel'}
    if command not in mapping: raise ValueError('unsupported release action')
    argv=[mapping[command],'--data-dir',str(bench.data_dir/'runs'),'--run-id',body['run_id']]
    for field, flag in [('target_id','--target-id'),('request_id','--request-id'),('authorization_id','--authorization-id'),('deployment_id','--deployment-id'),('effect_id','--effect-id')]:
        if body.get(field):
            import re
            if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.:-]{0,180}',str(body[field])): raise ValueError('无效操作标识')
            argv.extend([flag,str(body[field])])
    if command=='target':
        port=int(body.get('port',8766))
        if not 1024<=port<=65535: raise ValueError('invalid local agent port')
        argv.extend(['--port',str(port)])
    if body.get('rollback_only') is True: argv.append('--rollback-only')
    with contextlib.redirect_stdout(io.StringIO()): main(argv)
