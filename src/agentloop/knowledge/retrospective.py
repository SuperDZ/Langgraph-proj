"""用户主动触发的交付复盘：冻结证据、Curator 分析、产出待审提案。

规范约束（§6.4，REQ-029～031）：
- 正常仅对 COMPLETED 的 DELIVERY Run 允许完整复盘；异常复盘须用户显式选择
- 复盘使用独立子 Run：run_type=RETROSPECTIVE，不写父交付 Run 状态
- 同版本多次请求幂等；用户主动重做生成新版本
- Curator 输出全部落为 PENDING_HUMAN_REVIEW，不自动写入正式记忆
"""

from __future__ import annotations

from hashlib import sha256

from ..core.approvals.rbac import RBACService
from ..core.contracts.enums import (
    ActorType,
    EventType,
    RetrospectiveMode,
    RunPhase,
    RunStatus,
    RunType,
    TrustLevel,
)
from ..core.contracts.knowledge import RetrospectiveReport
from ..core.contracts.models import utc_now
from ..core.orchestration.store import InMemoryStore, atomic
from ..core.orchestration.state_transition import StateTransitionService
from .archive import canonical
from .memory import MemoryGovernanceService


class RetrospectiveError(ValueError):
    pass


class RetrospectiveService:
    def __init__(self, store: InMemoryStore, archive, rbac: RBACService,
                 memory: MemoryGovernanceService, *, transitions=None, clock=utc_now) -> None:
        self.store, self.archive, self.rbac = store, archive, rbac
        self.memory = memory
        self.transitions = transitions or StateTransitionService(store)
        self.clock = clock

    # ---------------- 触发（唯一入口，仅显式人工动作） ----------------

    @atomic
    def trigger(self, *, run_id: str, principal_id: str, curator,
                anomaly: bool = False, force_new: bool = False):
        """有权用户显式触发复盘。系统任何自动路径都不得调用本方法。"""
        run = self.store.get_run(run_id)
        self.rbac.require_human(principal_id)
        self.rbac.assert_project_access(principal_id, run.project_id)
        mode = RetrospectiveMode.ANOMALY if anomaly else RetrospectiveMode.FULL_DELIVERY
        if mode is RetrospectiveMode.FULL_DELIVERY:
            if run.phase is not RunPhase.DELIVERY or run.status is not RunStatus.COMPLETED:
                raise RetrospectiveError("完整复盘仅允许已完成的 DELIVERY Run；异常复盘须显式选择 --anomaly")
        elif run.status not in {RunStatus.FAILED, RunStatus.CANCELLED}:
            raise RetrospectiveError("异常复盘仅允许已终止（FAILED/CANCELLED）的 Run")
        delivered_version = run.baseline_versions.get("commit") or "uncommitted"
        version_key = f"{run_id}:{mode.value}:{delivered_version}"
        existing = self.store.runtime_get("retrospective", version_key)
        if existing and not force_new:
            return existing

        redo = 0
        if existing and force_new:
            redo = 1
            while self.store.runtime_get("retrospective", f"{version_key}:v{redo}"):
                redo += 1
        suffix = f"-v{redo}" if redo else ""
        storage_key = f"{version_key}:v{redo}" if redo else version_key
        child_id = "retro-" + sha256(version_key.encode()).hexdigest()[:20] + suffix
        self.store.append_event(
            run_id=run_id, event_type=EventType.RETROSPECTIVE_REQUESTED,
            actor_id=principal_id, actor_type=ActorType.HUMAN,
            payload_ref=f"child={child_id};mode={mode.value};version={delivered_version}",
            idempotency_key=f"{run_id}:RETRO_REQUESTED:{storage_key}",
        )
        if self.store.find_run(child_id) is None:
            self.transitions.create_run(
                run_id=child_id, run_type=RunType.RETROSPECTIVE, project_id=run.project_id,
                parent_run_id=run.run_id, trigger_source="USER_RETROSPECTIVE",
                config_snapshot_id=run.config_snapshot_id,
                baseline_versions=dict(run.baseline_versions),
            )
            self.transitions.transition(child_id, target_phase=RunPhase.RETROSPECTIVE,
                                        target_status=RunStatus.RUNNING)

        evidence = self._freeze_evidence(run)
        evidence_artifact = self.archive.put(
            run_id=child_id, kind="RETROSPECTIVE_EVIDENCE", producer="retrospective-freezer",
            value=evidence, trust=TrustLevel.VERIFIED_INTERNAL)
        report = RetrospectiveReport.model_validate(curator.analyze(evidence))
        self._validate_evidence_links(run_id, report)
        if (report.run_id != run_id or report.delivered_version != delivered_version
                or report.final_phase != run.phase.value or report.final_status != run.status.value):
            raise RetrospectiveError("复盘报告的运行身份、版本或终态与证据不符")
        report_artifact = self.archive.put(
            run_id=child_id, kind="RETROSPECTIVE_REPORT", producer="experience-curator",
            value={**report.model_dump(mode="json"), "mode": mode.value,
                   "evidence_artifact_id": evidence_artifact.artifact_id},
            trust=TrustLevel.MODEL_GENERATED)

        submitted = []
        for candidate in report.memory_candidates:
            proposal, accepted = self.memory.submit_memory_proposal(
                run_id=child_id, scope_type=candidate.scope_type, scope_id=candidate.scope_id,
                title=candidate.title, content=candidate.content,
                source_artifact_ids=candidate.source_artifact_ids,
                confidence=candidate.confidence, maturity=candidate.maturity,
                created_by="experience-curator", now=self.clock())
            submitted.append({"proposal_id": proposal.proposal_id,
                              "kind": "MEMORY", "accepted": accepted})
        for suggestion in report.runtime_suggestions:
            proposal = self.memory.submit_evolution_proposal(
                run_id=child_id, kind=suggestion.kind, target=suggestion.target,
                summary=suggestion.summary, verification_plan=suggestion.verification_plan,
                source_artifact_ids=suggestion.source_artifact_ids,
                created_by="experience-curator", now=self.clock())
            submitted.append({"proposal_id": proposal.proposal_id, "kind": "EVOLUTION"})

        if self.store.get_run(child_id).status is not RunStatus.COMPLETED:
            self.transitions.transition(child_id, target_status=RunStatus.COMPLETED)
        result = {"parent_run_id": run_id, "retrospective_run_id": child_id, "mode": mode.value,
                  "delivered_version": delivered_version, "version_key": version_key,
                  "report_artifact_id": report_artifact.artifact_id,
                  "evidence_artifact_id": evidence_artifact.artifact_id,
                  "proposals": submitted}
        self.store.runtime_put("retrospective", storage_key, result)
        self.store.runtime_put("retrospective_by_run", f"{run_id}:{child_id}", result)
        self.store.append_event(
            run_id=child_id, event_type=EventType.RETROSPECTIVE_COMPLETED,
            actor_id="experience-curator", actor_type=ActorType.SYSTEM,
            payload_ref=f"report={report_artifact.artifact_id};proposals={len(submitted)}",
            idempotency_key=f"{child_id}:RETRO_COMPLETED",
        )
        return result

    # ---------------- 证据冻结 ----------------

    def _freeze_evidence(self, run) -> dict:
        """只读冻结全部阶段原始产物与事件摘要；原文不可被摘要覆盖。"""
        artifacts = self.store.artifacts_for(run.run_id)
        events = self.store.events_for(run.run_id)
        histogram: dict[str, int] = {}
        for event in events:
            histogram[event.type.value] = histogram.get(event.type.value, 0) + 1
        return {
            "run": {"run_id": run.run_id, "phase": run.phase.value, "status": run.status.value,
                    "run_type": run.run_type.value, "project_id": run.project_id,
                    "baseline_versions": dict(run.baseline_versions)},
            "artifacts": [{"artifact_id": a.artifact_id, "type": a.type, "sha256": a.sha256,
                           "producer": a.producer_task_id, "trust": a.trust_level.value,
                           "created_at": a.created_at.isoformat(),
                           "body": self.archive.read(a.artifact_id, run_id=run.run_id)} for a in artifacts],
            "artifact_count": len(artifacts),
            "events": {"count": len(events), "type_histogram": histogram,
                       "event_log_digest": sha256(canonical(
                           [e.model_dump(mode="json") for e in events]).encode()).hexdigest(),
                       "records": [e.model_dump(mode="json") for e in events]},
            "gate_results": [{"gate_id": g.gate_id.value, "status": g.status.value,
                              "input_digest": g.input_digest} for g in self.store.gate_results_for(run.run_id)],
            "issues": [{"issue_id": i.issue_id, "category": i.category.value,
                        "severity": i.severity.value, "status": i.status.value}
                       for i in self.store.list_issues(run.run_id)],
            "deployments": [{"deployment_id": d.deployment_id, "status": d.status.value}
                            for d in self.store.deployments_for(run.run_id)],
            "releases": [{"release_id": r.release_id, "status": r.status.value}
                         for r in self.store.releases_for(run.run_id)],
            "frozen_at": self.clock().isoformat(),
        }

    def _validate_evidence_links(self, run_id: str, report: RetrospectiveReport) -> None:
        """Curator 报告中的证据引用必须指向冻结证据里的真实 Artifact，禁止编造。"""
        known = {a.artifact_id for a in self.store.artifacts_for(run_id)}
        referenced: set[str] = set()
        for entry in report.timeline:
            referenced.update(entry.source_artifact_ids)
        for stage in report.stage_evidence:
            referenced.update(stage.artifact_ids)
        for stat in report.defect_stats:
            referenced.update(stat.source_artifact_ids)
        for item in report.improvements:
            referenced.update(item.source_artifact_ids)
        for item in report.keep_practices:
            referenced.update(item.evidence_artifact_ids)
        for item in report.runtime_suggestions:
            referenced.update(item.source_artifact_ids)
        for item in report.memory_candidates:
            referenced.update(item.source_artifact_ids)
        missing = referenced - known
        if missing:
            raise RetrospectiveError(f"复盘报告引用了不存在的证据 Artifact：{sorted(missing)[:3]}")

    # ---------------- 查询 ----------------

    def retrospectives_for(self, run_id: str) -> list[dict]:
        return [r for r in self.store.runtime_list("retrospective_by_run")
                if r.get("parent_run_id") == run_id]

    def report(self, *, retrospective_run_id: str) -> dict:
        matches = [r for r in self.store.runtime_list("retrospective_by_run")
                   if r.get("retrospective_run_id") == retrospective_run_id]
        if not matches:
            raise RetrospectiveError(f"复盘子 Run 不存在：{retrospective_run_id}")
        record = matches[0]
        return {"record": record,
                "report": self.archive.read(record["report_artifact_id"], run_id=retrospective_run_id)}
