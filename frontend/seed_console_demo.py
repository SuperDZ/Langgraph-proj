"""控制台演示数据播种脚本（仅用于本地验证，验证完成后删除）。

写入的是与生产路径完全同构的持久记录：预算与用量流水、追加式事件、归档证据、
复盘子运行与报告、记忆提案与正式记忆、隔离 Skill 与 MCP 注册表。
"""
import sys
import uuid
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'src'))

from agentloop.core.orchestration import SQLiteStore
from agentloop.core.contracts.enums import (
    ActorType, EventType, MemoryMaturity, MemoryScopeType, MemoryStatus,
    ProposalStatus, RunPhase, RunStatus, RunType, TrustLevel,
)
from agentloop.core.contracts.knowledge import MemoryProposal, MemoryRecord
from agentloop.core.contracts.models import Run
from agentloop.knowledge import ArtifactArchive

DATA = ROOT / '.agentloop' / 'console-validation' / 'runs'
ROOT_RUN = 'demo-alpha'
RETRO_RUN = 'demo-alpha-retro-1'
PROJECT = 'phase1-demo'

EVENTS = [
    ('RUN_PHASE_CHANGED', 'system', ActorType.SYSTEM, 'INTAKE->SPEC;policy=v3'),
    ('GATE_EVALUATION_STARTED', 'gate-evaluator', ActorType.SYSTEM, 'gate=G1;policy=v3'),
    ('GATE_RESULT_RECORDED', 'gate-evaluator', ActorType.SYSTEM, 'gate=G1;status=REJECTED;issues=2'),
    ('APPROVAL_REQUEST_CREATED', 'system', ActorType.SYSTEM, 'subject=spec;request=apr-2291'),
    ('CLARIFICATION_REQUESTED', 'router', ActorType.AGENT, 'question=目标边界不明确'),
    ('ISSUE_RAISED', 'backend', ActorType.AGENT, 'severity=MAJOR;category=SCOPE'),
    ('ISSUE_ROUTED', 'router', ActorType.AGENT, 'department=engineering;leader=architect'),
    ('DEPARTMENT_ACCEPTED', 'architect', ActorType.AGENT, 'issue=ISS-1042;accepted=true'),
    ('CHECK_TRIGGERED', 'ci-runner', ActorType.SYSTEM, 'check=unit;scope=backend'),
    ('TEST_EXECUTED', 'ci-runner', ActorType.SYSTEM, 'suite=pytest;passed=80;failed=0'),
    ('BASELINE_CHANGED', 'architect', ActorType.AGENT, 'baseline=spec-v3->spec-v4'),
    ('WORKER_OUTPUT_RECORDED', 'backend', ActorType.AGENT, 'artifact=art-code-01;lines=418'),
    ('UNTRUSTED_INSTRUCTION_DETECTED', 'skill-sandbox', ActorType.SYSTEM, 'skill=quarantined-demo;pattern=prompt-injection'),
]

# 自定义治理动作走 RuntimeRepository.audit 的真实路径：RUNTIME_AUDIT 事件 + 归档体
AUDIT_ACTIONS = [
    ('BUDGET_BLOCKED', {'role': 'backend', 'request_id': 'req-778', 'reason': '根预算不足'}),
    ('MODEL_USAGE', {'role': 'backend', 'tokens': 48210, 'cost': 1180000}),
    ('SKILL_QUARANTINED', {'server_id': 'order-diff-kit', 'hash': 'skill-demo-0000'}),
    ('MCP_QUARANTINED', {'server_id': 'local-tools', 'hash': 'mcp-demo-0000'}),
]


def seed():
    with SQLiteStore(DATA / 'state.db') as store:
        archive = ArtifactArchive(DATA / 'artifacts', store)

        # ---- 预算与用量流水 ----
        store.runtime_put('budget', ROOT_RUN, {
            'root': ROOT_RUN, 'tokens': 200000, 'cost': 5000000,
            'initial_tokens': 200000, 'initial_cost': 5000000, 'overrun': False,
        })
        usages = [
            ('backend', 48210, 1180000, 'SETTLED'),
            ('frontend', 21460, 540000, 'SETTLED'),
            ('qa', 9800, 260000, 'SETTLED'),
            ('architect', 15300, 410000, 'SETTLED'),
            ('devops', 6120, 190000, 'RESERVED'),
        ]
        for index, (role, tokens, cost, status) in enumerate(usages):
            store.runtime_put('usage', f'{ROOT_RUN}-usage-{index}', {
                'id': f'{ROOT_RUN}-usage-{index}', 'root': ROOT_RUN, 'run_id': ROOT_RUN,
                'role': role, 'tokens': tokens, 'cost': cost,
                'reserved_tokens': tokens, 'reserved_cost': cost, 'status': status,
            })

        # ---- 追加式事件 ----
        for index, (etype, actor, actor_type, payload) in enumerate(EVENTS):
            store.append_event(
                run_id=ROOT_RUN, event_type=EventType(etype), actor_id=actor,
                actor_type=actor_type, payload_ref=payload,
                idempotency_key=f'{ROOT_RUN}:{etype}:{index}',
            )
        for index, (action, body) in enumerate(AUDIT_ACTIONS):
            audit_artifact = archive.put(
                run_id=ROOT_RUN, kind='RUNTIME_AUDIT', producer='runtime-policy',
                trust=TrustLevel.VERIFIED_INTERNAL, value={'action': action, **body},
            )
            store.append_event(
                run_id=ROOT_RUN, event_type=EventType.RUNTIME_AUDIT, actor_id='runtime-policy',
                actor_type=ActorType.SYSTEM, payload_ref=audit_artifact.artifact_id,
                idempotency_key=f'{ROOT_RUN}:runtime:{index:04d}',
            )

        # ---- 归档证据 ----
        evidence = []
        for kind, producer, trust, value in [
            ('SPEC_DOCUMENT', 'architect', TrustLevel.TRUSTED_FIRST_PARTY,
             {'title': '交付规格说明', 'sections': 9, 'constraints': ['本地演示', '禁止生产发布']}),
            ('SOURCE_DIFF', 'backend', TrustLevel.VERIFIED_INTERNAL,
             {'files': 12, 'insertions': 418, 'deletions': 96, 'module': 'order-service'}),
            ('TEST_REPORT', 'ci-runner', TrustLevel.VERIFIED_INTERNAL,
             {'suite': 'pytest', 'passed': 80, 'failed': 0, 'coverage': 0.83}),
            ('MODEL_OUTPUT', 'backend', TrustLevel.MODEL_GENERATED,
             {'summary': '完成订单状态机重构', 'claims': 6, 'verified_claims': 5}),
        ]:
            artifact = archive.put(run_id=ROOT_RUN, kind=kind, producer=producer, value=value, trust=trust)
            evidence.append(artifact)

        # ---- 复盘子运行 + 报告 ----
        store.put_run(Run(
            run_id=RETRO_RUN, run_type=RunType.RETROSPECTIVE, parent_run_id=ROOT_RUN,
            root_run_id=ROOT_RUN, project_id=PROJECT, phase=RunPhase.RETROSPECTIVE,
            status=RunStatus.COMPLETED, state_version=1, baseline_versions={},
            trigger_source='HUMAN', config_snapshot_id='ui-demo',
        ))
        report_artifact = archive.put(
            run_id=RETRO_RUN, kind='RETROSPECTIVE_REPORT', producer='experience-curator',
            trust=TrustLevel.VERIFIED_INTERNAL,
            value={
                'summary': '交付过程基本达成目标，但预算预占与澄清节奏存在可改进空间',
                'timeline': [
                    {'stage': 'SPEC', 'outcome': '通过', 'detail': 'G1 二次评估通过'},
                    {'stage': 'BUILD', 'outcome': '通过', 'detail': '订单状态机重构完成'},
                    {'stage': 'VERIFY', 'outcome': '部分', 'detail': '80 项测试通过，1 项门禁曾被阻断'},
                ],
                'defect_stats': [{'category': 'SCOPE', 'severity': 'MAJOR', 'count': 2}],
                'improvements': [
                    '澄清问题应在 G1 之前一次性批量发出，避免串行等待',
                    '预算预占阈值建议下调至单角色 60%，减少硬阻断',
                ],
                'keep_practices': ['证据冻结后再复盘，结论可追溯'],
                'runtime_suggestions': ['为 backend 角色配置独立预算上限'],
                'memory_candidates': ['澄清问题批量发出可显著缩短交付周期'],
            },
        )
        evidence_artifact = archive.put(
            run_id=RETRO_RUN, kind='FROZEN_EVIDENCE', producer='experience-curator',
            trust=TrustLevel.VERIFIED_INTERNAL,
            value={'run_id': ROOT_RUN, 'artifact_count': len(evidence),
                   'event_count': len(EVENTS), 'frozen_at': '2026-11-06T06:00:00Z'},
        )
        store.runtime_put('retrospective_by_run', f'{ROOT_RUN}:{RETRO_RUN}', {
            'parent_run_id': ROOT_RUN, 'retrospective_run_id': RETRO_RUN, 'mode': 'FULL_DELIVERY',
            'delivered_version': 'spec-v4', 'version_key': 'spec-v4',
            'report_artifact_id': report_artifact.artifact_id,
            'evidence_artifact_id': evidence_artifact.artifact_id, 'proposals': [],
        })

        # ---- 记忆提案 ----
        proposals = [
            ('澄清问题应在 G1 之前一次性批量发出，避免串行等待',
             '本轮交付中 3 次澄清串行发生，累计等待约 42 分钟，拖长了整体周期。',
             MemoryScopeType.DEPARTMENT, 'engineering', 0.82, MemoryMaturity.CANDIDATE, False),
            ('后端角色预算上限应独立于根预算，避免单体角色吃掉全部额度',
             'backend 角色单次调用预占了根预算的 48%，导致 qa 角色被硬阻断。',
             MemoryScopeType.AGENT, 'backend', 0.71, MemoryMaturity.OBSERVED, False),
            ('外部 Issue 描述可能携带提示注入，路由前必须做指令清洗',
             '在导入的 Issue 正文中检出越权指令片段。',
             MemoryScopeType.SHARED, '', 0.94, MemoryMaturity.CANDIDATE, True),
        ]
        for index, (title, content, scope_type, scope_id, confidence, maturity, flagged) in enumerate(proposals):
            store.put_memory_proposal(MemoryProposal(
                proposal_id=f'memprop-demo-{index}', run_id=RETRO_RUN,
                scope_type=scope_type, scope_id=scope_id, title=title, content=content,
                source_artifact_ids=[evidence_artifact.artifact_id],
                confidence=confidence, maturity=maturity,
                status=ProposalStatus.PENDING_HUMAN_REVIEW, injection_flagged=flagged,
                created_by='experience-curator',
            ))

        # ---- 正式记忆 ----
        memories = [
            ('G1 门禁通过前必须完成全部澄清',
             '任何未回答的澄清问题都会让 G1 结论失效，返工成本远高于提前确认。',
             MemoryScopeType.PROJECT, PROJECT, 1, MemoryStatus.ACTIVE, 0.9),
            ('测试证据必须绑定提交哈希',
             '脱离 commit 的测试报告不可作为门禁证据，已在两次评审中被驳回。',
             MemoryScopeType.DEPARTMENT, 'engineering', 2, MemoryStatus.DEPRECATED, 0.76),
        ]
        for index, (title, content, scope_type, scope_id, version, status, confidence) in enumerate(memories):
            store.put_memory(MemoryRecord(
                memory_id=f'memory-demo-{index}', origin_run_id=RETRO_RUN,
                origin_proposal_id=f'memprop-demo-{index}', scope_type=scope_type,
                scope_id=scope_id, title=title, content=content,
                source_artifact_ids=[evidence_artifact.artifact_id],
                confidence=confidence, status=status, version=version,
                approved_by='demo-owner',
            ))

        # ---- 隔离 Skill ----
        skills = [
            ('order-diff-kit', '对比订单服务的接口差异，生成迁移清单。',
             ['CONTAINS_SCRIPTS_NEVER_EXECUTED', 'LICENSE_UNDECLARED'], 'QUARANTINED'),
            ('contract-lint-helper', '校验 API 契约与实现是否一致。',
             ['LICENSE_UNDECLARED'], 'APPROVED'),
        ]
        for index, (name, description, risks, status) in enumerate(skills):
            version = f'skill-demo-{index:04d}'
            skill_artifact = archive.put(
                run_id=ROOT_RUN, kind='QUARANTINED_SKILL', producer='skill-import',
                trust=TrustLevel.UNTRUSTED_EXTERNAL,
                value={'files': {'skill.json': {'name': name, 'description': description}},
                       'metadata': {'name': name}, 'source': 'local-import', 'risks': risks},
            )
            store.runtime_put('skill', version, {
                'hash': version, 'name': name, 'description': description,
                'artifact_id': skill_artifact.artifact_id, 'source_run': ROOT_RUN,
                'source': 'local-import', 'risks': risks, 'dependencies': [],
                'status': status,
            })

        # ---- MCP 注册表 ----
        mcps = [
            ('local-tools', 'http', 'http://127.0.0.1:8767/mcp', 'QUARANTINED',
             {'search_code': {'capability': 'read', 'mutating': False},
              'run_tests': {'capability': 'execute', 'mutating': True}}),
            ('docs-index', 'http', 'http://127.0.0.1:8768/mcp', 'APPROVED',
             {'lookup': {'capability': 'read', 'mutating': False}}),
        ]
        for index, (server_id, transport, url, status, tools) in enumerate(mcps):
            version = f'mcp-demo-{index:04d}'
            store.runtime_put('mcp_version', version, {
                'hash': version,
                'config': {'server_id': server_id, 'transport': transport, 'url': url,
                           'timeout': 20, 'tools': tools},
                'files': {}, 'project': PROJECT, 'run_id': ROOT_RUN, 'status': status,
            })

        print('seeded demo-alpha with:')
        print('  budget + %d usage receipts' % len(usages))
        print('  %d appended events' % len(EVENTS))
        print('  %d archived artifacts' % len(evidence))
        print('  retrospective %s' % RETRO_RUN)
        print('  %d memory proposals / %d memories' % (len(proposals), len(memories)))
        print('  %d skills / %d mcp versions' % (len(skills), len(mcps)))


if __name__ == '__main__':
    seed()
