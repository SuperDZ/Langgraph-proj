"""Phase 4 知识库契约：长期记忆提案、正式记忆、演进提案与复盘报告。

规范约束（§6）：
- 原始产物不可被事后摘要覆盖；每条记忆必须回溯到 source_artifact_ids
- Curator 只能产生 OBSERVED/CANDIDATE 的 PENDING_HUMAN_REVIEW 提案
- 审批状态（ProposalStatus）与内容成熟度（MemoryMaturity）正交
- 冲突记忆标记失效并被新版本取代，不静默覆盖
"""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from pydantic import Field, field_validator

from .enums import EvolutionKind, MemoryMaturity, MemoryScopeType, MemoryStatus, ProposalStatus
from .models import StrictModel, utc_now


def _new_id(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex}"


class MemoryProposal(StrictModel):
    """待人工审查的长期记忆提案。未经批准不得进入任何可检索命名空间。"""

    proposal_id: str = Field(default_factory=lambda: _new_id("memprop"))
    run_id: str
    scope_type: MemoryScopeType
    scope_id: str = ""
    title: str = Field(min_length=1, max_length=200)
    content: str = Field(min_length=1)
    source_artifact_ids: list[str] = Field(min_length=1)
    expires_at: datetime | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    maturity: MemoryMaturity = MemoryMaturity.OBSERVED
    status: ProposalStatus = ProposalStatus.PENDING_HUMAN_REVIEW
    injection_flagged: bool = False
    created_by: str
    created_at: datetime = Field(default_factory=utc_now)
    reviewed_by: str | None = None
    reviewed_at: datetime | None = None
    review_reason: str | None = None
    published_memory_id: str | None = None

    @field_validator("maturity")
    @classmethod
    def _curator_cannot_self_publish(cls, value: MemoryMaturity) -> MemoryMaturity:
        if value not in {MemoryMaturity.OBSERVED, MemoryMaturity.CANDIDATE}:
            raise ValueError("提案成熟度只能是 OBSERVED 或 CANDIDATE；发布由人工审批赋予")
        return value

    @field_validator("scope_id")
    @classmethod
    def _shared_has_empty_scope(cls, value: str, info) -> str:
        if info.data.get("scope_type") is MemoryScopeType.SHARED:
            return ""
        if not value:
            raise ValueError("非 SHARED 命名空间必须指明 scope_id")
        return value


class MemoryRecord(StrictModel):
    """经人工批准进入正式命名空间的长期记忆。版本化、可追溯、可撤销。"""

    memory_id: str = Field(default_factory=lambda: _new_id("memory"))
    origin_run_id: str
    origin_proposal_id: str
    scope_type: MemoryScopeType
    scope_id: str = ""
    title: str = Field(min_length=1, max_length=200)
    content: str
    source_artifact_ids: list[str] = Field(min_length=1)
    expires_at: datetime | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    status: MemoryStatus = MemoryStatus.ACTIVE
    version: int = Field(ge=1, default=1)
    approved_by: str
    approved_at: datetime = Field(default_factory=utc_now)
    superseded_by: str | None = None


class EvolutionProposal(StrictModel):
    """Skill/提示词/配置的演进提案。与长期记忆治理分离（AC-53）。"""

    proposal_id: str = Field(default_factory=lambda: _new_id("evo"))
    run_id: str
    kind: EvolutionKind
    target: str = Field(min_length=1, max_length=200)
    summary: str = Field(min_length=1)
    verification_plan: str = Field(min_length=1)
    source_artifact_ids: list[str] = Field(min_length=1)
    status: ProposalStatus = ProposalStatus.PENDING_HUMAN_REVIEW
    created_by: str
    created_at: datetime = Field(default_factory=utc_now)
    reviewed_by: str | None = None
    reviewed_at: datetime | None = None
    review_reason: str | None = None
    verification_result: str | None = None


# --------------------------------------------------------------------------
# 复盘报告（§6.8 固定模板；每个结论必须携带真实证据）
# --------------------------------------------------------------------------

class TimelineEntry(StrictModel):
    stage: str
    note: str
    source_artifact_ids: list[str] = Field(default_factory=list)


class StageEvidence(StrictModel):
    stage: str
    artifact_ids: list[str] = Field(min_length=1)


class DefectStat(StrictModel):
    severity: str
    count: int = Field(ge=0)
    responsibility: str
    source_artifact_ids: list[str] = Field(default_factory=list)


class Improvement(StrictModel):
    issue: str
    root_cause: str
    action: str
    verification: str
    estimated_benefit: str = ""
    source_artifact_ids: list[str] = Field(min_length=1)


class KeepPractice(StrictModel):
    practice: str
    applicability: str
    evidence_artifact_ids: list[str] = Field(min_length=1)


class RuntimeSuggestion(StrictModel):
    kind: EvolutionKind
    target: str
    summary: str
    verification_plan: str
    source_artifact_ids: list[str] = Field(min_length=1)


class MemoryCandidate(StrictModel):
    scope_type: MemoryScopeType
    scope_id: str = ""
    title: str
    content: str
    confidence: float = Field(ge=0.0, le=1.0)
    maturity: MemoryMaturity = MemoryMaturity.OBSERVED
    source_artifact_ids: list[str] = Field(min_length=1)


class RetrospectiveReport(StrictModel):
    """复盘报告固定输出模板。证据不足的结论必须显式标注待验证。"""

    run_id: str
    delivered_version: str
    final_phase: str
    final_status: str
    summary: str
    timeline: list[TimelineEntry] = Field(min_length=1)
    stage_evidence: list[StageEvidence] = Field(min_length=1)
    defect_stats: list[DefectStat] = Field(default_factory=list)
    improvements: list[Improvement] = Field(default_factory=list)
    keep_practices: list[KeepPractice] = Field(min_length=1)
    runtime_suggestions: list[RuntimeSuggestion] = Field(default_factory=list)
    memory_candidates: list[MemoryCandidate] = Field(default_factory=list)
    regression_checklist: list[str] = Field(default_factory=list)
    open_risks: list[str] = Field(default_factory=list)
