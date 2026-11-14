"""长期记忆治理：提案 → 人工审查 → 版本化发布 → 撤销/废弃。

规范约束（§6.4/§6.6/§6.7，REQ-030/031）：
- 所有长期记忆一律先创建 PENDING_HUMAN_REVIEW 提案，Curator 不得自行发布
- 治理转移（批准/拒绝/撤销）只接受具备 ``memory_reviewer`` 角色的真人
- 不可信内容中的治理指令在提交时即拒绝，不进入待审队列
- 同命名空间同标题冲突时旧版本标记 DEPRECATED 并记录 superseded_by，不静默覆盖
- 检索只返回 ACTIVE 记录；待审提案对运行中 Agent 完全不可见
"""

from __future__ import annotations

from datetime import datetime

from ..core.approvals.rbac import AccessDenied, RBACService
from ..core.contracts.enums import (
    ActorType,
    EventType,
    EvolutionKind,
    GOVERNANCE_INJECTION_PATTERNS,
    MemoryMaturity,
    MemoryScopeType,
    MemoryStatus,
    ProposalStatus,
)
from ..core.contracts.knowledge import EvolutionProposal, MemoryProposal, MemoryRecord
from ..core.contracts.models import utc_now
from ..core.orchestration.store import InMemoryStore, atomic

CURATOR_ACTOR = "experience-curator"
MEMORY_REVIEWER_ROLE = "memory_reviewer"


def contains_governance_injection(*texts: str) -> str | None:
    """返回命中的注入模式；未命中返回 None。"""
    for text in texts:
        lowered = text.lower()
        for pattern in GOVERNANCE_INJECTION_PATTERNS:
            if pattern in lowered:
                return pattern
    return None


class MemoryGovernanceError(ValueError):
    """提案提交或治理决策被拒绝。"""


class MemoryGovernanceService:
    """知识治理的唯一入口。Curator 输出必须经本服务落为待审提案。"""

    def __init__(self, store: InMemoryStore, rbac: RBACService, *, clock=utc_now) -> None:
        self.store, self.rbac, self.clock = store, rbac, clock

    # ---------------- 提案提交（Curator / 人工候选） ----------------

    def _require_evidence(self, artifact_ids: list[str], run_id: str) -> None:
        project = self._origin_project(run_id)
        for artifact_id in artifact_ids:
            try:
                artifact = self.store.get_artifact(artifact_id)
                if self._origin_project(artifact.run_id) != project:
                    raise MemoryGovernanceError("证据不得跨项目引用")
            except KeyError as exc:
                raise MemoryGovernanceError(f"证据 Artifact 不存在：{artifact_id}") from exc

    @atomic
    def submit_memory_proposal(
        self,
        *,
        run_id: str,
        scope_type: MemoryScopeType,
        scope_id: str,
        title: str,
        content: str,
        source_artifact_ids: list[str],
        confidence: float,
        maturity=None,
        created_by: str = CURATOR_ACTOR,
        now: datetime | None = None,
    ) -> tuple[MemoryProposal, bool]:
        """提交记忆提案。命中治理注入的内容直接拒绝，不进入待审队列。

        返回 ``(proposal, accepted)``；``accepted=False`` 表示因注入被拒绝，
        记录仅用于审计。
        """
        moment = now or self.clock()
        self._require_evidence(source_artifact_ids, run_id)
        injection = contains_governance_injection(title, content)
        proposal = MemoryProposal(
            run_id=run_id, scope_type=scope_type, scope_id=scope_id,
            title=title, content=content, source_artifact_ids=source_artifact_ids,
            confidence=confidence,
            maturity=maturity if maturity is not None else MemoryMaturity.OBSERVED,
            created_by=created_by, created_at=moment,
        )
        if injection is not None:
            proposal.injection_flagged = True
            proposal.status = ProposalStatus.REJECTED
            proposal.review_reason = f"governance injection pattern: {injection}"
        self.store.put_memory_proposal(proposal)
        self.store.append_event(
            run_id=run_id, event_type=EventType.MEMORY_PROPOSAL_SUBMITTED,
            actor_id=created_by, actor_type=ActorType.AGENT,
            payload_ref=(f"proposal={proposal.proposal_id};scope={scope_type.value}/{scope_id};"
                         f"accepted={injection is None}"),
            idempotency_key=f"{run_id}:MEMORY_SUBMITTED:{proposal.proposal_id}",
        )
        return proposal, injection is None

    @atomic
    def submit_evolution_proposal(
        self,
        *,
        run_id: str,
        kind: EvolutionKind,
        target: str,
        summary: str,
        verification_plan: str,
        source_artifact_ids: list[str],
        created_by: str = CURATOR_ACTOR,
        now: datetime | None = None,
    ) -> EvolutionProposal:
        moment = now or self.clock()
        self._require_evidence(source_artifact_ids, run_id)
        if contains_governance_injection(summary, target) is not None:
            raise MemoryGovernanceError("演进提案包含治理注入内容，拒绝提交")
        proposal = EvolutionProposal(
            run_id=run_id, kind=kind, target=target, summary=summary,
            verification_plan=verification_plan, source_artifact_ids=source_artifact_ids,
            created_by=created_by, created_at=moment,
        )
        self.store.put_evolution_proposal(proposal)
        self.store.append_event(
            run_id=run_id, event_type=EventType.EVOLUTION_PROPOSAL_SUBMITTED,
            actor_id=created_by, actor_type=ActorType.AGENT,
            payload_ref=f"proposal={proposal.proposal_id};kind={kind.value};target={target}",
            idempotency_key=f"{run_id}:EVOLUTION_SUBMITTED:{proposal.proposal_id}",
        )
        return proposal

    # ---------------- 治理决策（仅真人 memory_reviewer） ----------------

    def _require_reviewer(self, principal_id: str, project_id: str, moment: datetime) -> None:
        self.rbac.require_human(principal_id)
        self.rbac.assert_project_access(principal_id, project_id, moment)
        self.rbac.require_role(principal_id, MEMORY_REVIEWER_ROLE, project_id)

    @atomic
    def decide_memory(self, *, proposal_id: str, decision, principal_id: str,
                      reason: str = "", now: datetime | None = None) -> MemoryProposal:
        from ..core.contracts.enums import ApprovalDecision

        if decision not in {ApprovalDecision.APPROVE, ApprovalDecision.REJECT}:
            raise MemoryGovernanceError("decision 只能是 APPROVE 或 REJECT")
        moment = now or self.clock()
        proposal = self.store.get_memory_proposal(proposal_id)
        if proposal.status is not ProposalStatus.PENDING_HUMAN_REVIEW:
            raise MemoryGovernanceError(f"提案状态为 {proposal.status.value}，不可再决策")
        project = self._origin_project(proposal.run_id)
        self._require_reviewer(principal_id, project, moment)
        proposal.reviewed_by = principal_id
        proposal.reviewed_at = moment
        proposal.review_reason = reason or None
        if decision is ApprovalDecision.REJECT:
            proposal.status = ProposalStatus.REJECTED
            self.store.put_memory_proposal(proposal)
            self._decided_event(proposal, "REJECTED", principal_id)
            return proposal
        record = self._publish(proposal, principal_id, moment)
        proposal.status = ProposalStatus.APPROVED
        proposal.published_memory_id = record.memory_id
        self.store.put_memory_proposal(proposal)
        self._decided_event(proposal, "APPROVED", principal_id, memory_id=record.memory_id,
                            version=record.version)
        return proposal

    def _origin_project(self, run_id: str) -> str:
        return self.store.get_run(run_id).project_id

    def _publish(self, proposal: MemoryProposal, principal_id: str, moment: datetime) -> MemoryRecord:
        """发布为正式记忆；同命名空间同标题的 ACTIVE 旧版本标记 DEPRECATED。"""
        previous = [
            m for m in self.store.memories()
            if m.scope_type is proposal.scope_type and m.scope_id == proposal.scope_id
            and m.title == proposal.title
            and self._origin_project(m.origin_run_id) == self._origin_project(proposal.run_id)
        ]
        record = MemoryRecord(
            origin_run_id=proposal.run_id, origin_proposal_id=proposal.proposal_id,
            scope_type=proposal.scope_type, scope_id=proposal.scope_id,
            title=proposal.title, content=proposal.content,
            source_artifact_ids=proposal.source_artifact_ids, confidence=proposal.confidence,
            expires_at=proposal.expires_at, version=1, approved_by=principal_id, approved_at=moment,
        )
        if previous:
            old = max(previous, key=lambda m: m.version)
            record.version = old.version + 1
            for prior in previous:
                if prior.status is MemoryStatus.ACTIVE:
                    prior.status = MemoryStatus.DEPRECATED
                    prior.superseded_by = record.memory_id
                    self.store.put_memory(prior)
        self.store.put_memory(record)
        return record

    def _decided_event(self, proposal: MemoryProposal, outcome: str, principal_id: str, *,
                       memory_id: str | None = None, version: int | None = None) -> None:
        payload = f"proposal={proposal.proposal_id};{outcome};reviewer={principal_id}"
        if memory_id:
            payload += f";memory={memory_id};version={version}"
        self.store.append_event(
            run_id=proposal.run_id, event_type=EventType.MEMORY_PROPOSAL_DECIDED,
            actor_id=principal_id, actor_type=ActorType.HUMAN, payload_ref=payload,
            idempotency_key=f"{proposal.run_id}:MEMORY_DECIDED:{proposal.proposal_id}",
        )

    @atomic
    def decide_evolution(self, *, proposal_id: str, decision, principal_id: str,
                         verification_result: str = "", reason: str = "",
                         now: datetime | None = None) -> EvolutionProposal:
        """Skill/提示词/配置演进提案的审批。

        与记忆审批分离（AC-53）：批准必须附带验证结果，且不修改任何 Agent
        生效配置——发布到生效配置由 Skills/配置管理另行执行。
        """
        from ..core.contracts.enums import ApprovalDecision

        if decision not in {ApprovalDecision.APPROVE, ApprovalDecision.REJECT}:
            raise MemoryGovernanceError("decision 只能是 APPROVE 或 REJECT")
        moment = now or self.clock()
        proposal = self.store.get_evolution_proposal(proposal_id)
        if proposal.status is not ProposalStatus.PENDING_HUMAN_REVIEW:
            raise MemoryGovernanceError(f"提案状态为 {proposal.status.value}，不可再决策")
        project = self._origin_project(proposal.run_id)
        self._require_reviewer(principal_id, project, moment)
        proposal.reviewed_by = principal_id
        proposal.reviewed_at = moment
        proposal.review_reason = reason or None
        if decision is ApprovalDecision.APPROVE:
            if not verification_result.strip():
                raise MemoryGovernanceError("批准演进提案必须附带验证结果（§6.6）")
            proposal.verification_result = verification_result
        proposal.status = ProposalStatus(
            "APPROVED" if decision is ApprovalDecision.APPROVE else "REJECTED")
        self.store.put_evolution_proposal(proposal)
        self.store.append_event(
            run_id=proposal.run_id, event_type=EventType.EVOLUTION_PROPOSAL_DECIDED,
            actor_id=principal_id, actor_type=ActorType.HUMAN,
            payload_ref=(f"proposal={proposal.proposal_id};{proposal.status.value};"
                         f"reviewer={principal_id};target={proposal.target}"),
            idempotency_key=f"{proposal.run_id}:EVOLUTION_DECIDED:{proposal.proposal_id}",
        )
        return proposal

    @atomic
    def revoke_memory(self, *, memory_id: str, principal_id: str, reason: str,
                      now: datetime | None = None) -> MemoryRecord:
        """撤销正式记忆：立即停止检索，保留审计与版本链。"""
        moment = now or self.clock()
        record = self.store.get_memory(memory_id)
        project = self._origin_project(record.origin_run_id)
        self._require_reviewer(principal_id, project, moment)
        if record.status is MemoryStatus.REVOKED:
            return record
        record.status = MemoryStatus.REVOKED
        self.store.put_memory(record)
        self.store.append_event(
            run_id=record.origin_run_id, event_type=EventType.MEMORY_REVOKED,
            actor_id=principal_id, actor_type=ActorType.HUMAN,
            payload_ref=f"memory={memory_id};version={record.version};reviewer={principal_id};reason={reason}",
            idempotency_key=f"{record.origin_run_id}:MEMORY_REVOKED:{memory_id}:{record.version}",
        )
        return record

    # ---------------- 检索（只读正式记忆；待审提案不可见） ----------------

    @atomic
    def rollback_memory(self, *, memory_id: str, principal_id: str, reason: str) -> MemoryRecord:
        record = self.store.get_memory(memory_id)
        project = self._origin_project(record.origin_run_id)
        self._require_reviewer(principal_id, project, self.clock())
        if (record.status is not MemoryStatus.DEPRECATED or not reason.strip()
                or (record.expires_at is not None and record.expires_at <= self.clock())):
            raise MemoryGovernanceError("只能显式回滚已废弃版本，且必须填写原因")
        self._require_evidence(record.source_artifact_ids, record.origin_run_id)
        for current in self.store.memories():
            if (current.status is MemoryStatus.ACTIVE and current.title == record.title
                and current.scope_type is record.scope_type and current.scope_id == record.scope_id
                and self._origin_project(current.origin_run_id) == project):
                current.status = MemoryStatus.DEPRECATED
                current.superseded_by = record.memory_id
                self.store.put_memory(current)
        record.status = MemoryStatus.ACTIVE
        record.superseded_by = None
        self.store.put_memory(record)
        from uuid import uuid4
        self.store.append_event(run_id=record.origin_run_id, event_type=EventType.RUNTIME_AUDIT,
            actor_id=principal_id, actor_type=ActorType.HUMAN,
            payload_ref=f"MEMORY_ROLLBACK:{memory_id};reason={reason}",
            idempotency_key=f"{record.origin_run_id}:MEMORY_ROLLBACK:{uuid4().hex}")
        return record

    def search(self, *, principal_id: str, scope_type: MemoryScopeType | None = None,
               scope_id: str | None = None, project_id: str | None = None,
               query: str | None = None, now: datetime | None = None) -> list[MemoryRecord]:
        """按权限过滤检索已批准记忆。待审/被拒提案永远不会出现在结果中。"""
        moment = now or self.clock()
        principal = self.rbac.get_principal(principal_id)
        if principal.status != "ACTIVE":
            return []
        records = [m for m in self.store.memories() if m.status is MemoryStatus.ACTIVE and (m.expires_at is None or m.expires_at > moment)]
        if scope_type is not None:
            records = [m for m in records if m.scope_type is scope_type]
        if scope_id is not None:
            records = [m for m in records if m.scope_id == scope_id]
        if project_id is not None:
            records = [m for m in records if self._origin_project_safe(m.origin_run_id) == project_id]
        if query:
            lowered = query.lower()
            records = [m for m in records
                       if lowered in m.title.lower() or lowered in m.content.lower()]
        visible = []
        for record in records:
            origin_project = self._origin_project_safe(record.origin_run_id)
            if record.scope_type is MemoryScopeType.AGENT and principal_id != record.scope_id:
                # 专属记忆仅本 Agent 与项目内有权限的人类可见
                try:
                    self.rbac.require_human(principal_id)
                    self.rbac.assert_project_access(principal_id, origin_project, moment)
                except (AccessDenied, KeyError):
                    continue
            else:
                try:
                    self.rbac.assert_project_access(principal_id, origin_project, moment)
                except (AccessDenied, KeyError):
                    continue
            visible.append(record)
        return visible

    def _origin_project_safe(self, run_id: str) -> str | None:
        try:
            return self.store.get_run(run_id).project_id
        except KeyError:
            return None

    def pending_review(self, *, principal_id: str, run_id: str | None = None,
                       now: datetime | None = None) -> list[MemoryProposal]:
        """审核人视角的待审队列；运行中 Agent 不得调用。"""
        moment = now or self.clock()
        proposals = [p for p in self.store.memory_proposals_for(run_id)
                     if p.status is ProposalStatus.PENDING_HUMAN_REVIEW]
        if not proposals:
            return []
        visible = []
        for proposal in proposals:
            try:
                self._require_reviewer(principal_id, self._origin_project(proposal.run_id), moment)
            except AccessDenied:
                continue
            visible.append(proposal)
        return visible

    @atomic
    def publish_evolution(self, *, proposal_id, skill_hash, role, verification_artifact_id, principal_id, archive):
        proposal = self.store.get_evolution_proposal(proposal_id)
        project = self._origin_project(proposal.run_id)
        self._require_reviewer(principal_id, project, self.clock())
        if proposal.status is not ProposalStatus.APPROVED or proposal.kind is not EvolutionKind.SKILL:
            raise MemoryGovernanceError('演进提案尚未人工批准')
        evidence = self.store.get_artifact(verification_artifact_id)
        self._require_evidence([verification_artifact_id], proposal.run_id)
        from ..core.contracts.enums import TrustLevel
        if evidence.type != 'SKILL_VERIFICATION' or evidence.trust_level is not TrustLevel.VERIFIED_INTERNAL:
            raise MemoryGovernanceError('需要可信执行器产生的 Skill 验证证据')
        result = archive.read(verification_artifact_id, run_id=evidence.run_id)
        if result.get('skill_hash') != skill_hash or result.get('decision') != 'PASS' or result.get('failed') != 0:
            raise MemoryGovernanceError('测试证据未通过或未绑定指定 Skill 版本')
        from ..core.runtime.skills import SkillRegistry
        from ..core.runtime.configuration import RuntimeRepository
        registry = SkillRegistry(RuntimeRepository(self.store, archive), self.rbac)
        record = self.store.runtime_get('skill', skill_hash)
        if not record or record['name'] != proposal.target:
            raise MemoryGovernanceError('Skill 名称与演进目标不一致')
        saved = self.store.runtime_get('evolution_publication', proposal_id)
        if saved:
            if saved['hash'] != skill_hash or saved['role'] != role:
                raise MemoryGovernanceError('已发布提案不可替换版本或角色')
            return saved
        registry.approve(skill_hash, principal_id=principal_id, project_id=project, accepted_risks=record['risks'])
        registry.bind(skill_hash, principal_id=principal_id, project_id=project, role=role)
        publication = {'proposal_id':proposal_id,'hash':skill_hash,'role':role,'verification':verification_artifact_id,'published_by':principal_id}
        self.store.runtime_put('evolution_publication',proposal_id,publication)
        return publication
