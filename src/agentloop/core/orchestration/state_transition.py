"""状态迁移服务：三套白名单的唯一执行入口。

规范约束（§2.2 / §8.5）：
- 任何检查与状态切换必须经服务端 StateTransitionService
- 在单事务内检查 state_version（乐观锁）并追加 ExecutionEvent
- 失败不能部分落库
- phase 与 status 必须按复合守卫共同检查，而不是各自通过即放行
- 非法跃迁返回 409 INVALID_TRANSITION 且不修改原状态

这个模块里没有任何 LLM 调用。
"""

from __future__ import annotations

from datetime import datetime
from typing import Literal

from ..contracts.enums import (
    ActorType,
    EventType,
    GateStatus,
    RunPhase,
    RunStatus,
    RunType,
)
from ..contracts.models import ExecutionEvent, GateResult, Run, utc_now
from ..contracts.transitions import (
    GATE_STATUS_TRANSITIONS,
    RUN_STATUS_TRANSITIONS,
    allowed_phase_targets,
    check_composite_guard,
)
from .store import ConcurrentModificationError, InMemoryStore, atomic

ErrorCode = Literal[
    "INVALID_TRANSITION",
    "STATE_VERSION_CONFLICT",
    "INVALID_COMBINATION",
    "GUARD_FAILED",
]


class TransitionRejected(Exception):
    """非法跃迁。调用方据此返回 409 INVALID_TRANSITION。"""

    def __init__(
        self,
        code: ErrorCode,
        message: str,
        run_id: str,
        *,
        current_phase: RunPhase | None = None,
        current_status: RunStatus | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.run_id = run_id
        self.current_phase = current_phase
        self.current_status = current_status

    def to_payload(self) -> dict:
        return {
            "error": self.code,
            "message": self.message,
            "run_id": self.run_id,
            "phase": self.current_phase.value if self.current_phase else None,
            "status": self.current_status.value if self.current_status else None,
        }


class StateTransitionService:
    """Run 与 GateResult 的状态机守卫。"""

    def __init__(self, store: InMemoryStore, *, allow_simulated_deployment=False, deployment_guard=None) -> None:
        self.store = store
        self.allow_simulated_deployment = allow_simulated_deployment
        self.deployment_guard = deployment_guard

    @atomic
    def bind_baseline(self, run_id, *, key, digest, expected_version):
        allowed = {"spec": RunPhase.PRODUCT, "architecture": RunPhase.ARCHITECTURE,
                   "commit": RunPhase.ENGINEERING}
        current = self.store.get_run(run_id)
        if key not in allowed or current.phase is not allowed[key] or current.status is not RunStatus.RUNNING:
            raise TransitionRejected("GUARD_FAILED", "基线只能在对应阶段绑定", run_id)
        if current.state_version != expected_version:
            raise TransitionRejected("STATE_VERSION_CONFLICT", "基线版本冲突", run_id)
        if current.baseline_versions.get(key) == digest:
            return current
        updated = current.model_copy(deep=True)
        updated.baseline_versions[key] = digest
        updated.state_version += 1
        self.store.cas_run(updated, expected_version)
        for gate in self.store.gate_results_for(run_id):
            if (key != "commit" or gate.gate_id.value != "G1") and gate.status in {GateStatus.PENDING, GateStatus.PASSED}:
                self.transition_gate(gate, GateStatus.STALE)
        self.store.append_event(run_id=run_id, event_type=EventType.BASELINE_CHANGED,
            actor_id="orchestrator", actor_type=ActorType.SYSTEM, payload_ref=f"{key}={digest}",
            idempotency_key=f"{run_id}:BASELINE:{updated.state_version}")
        return updated

    # ------------------------------------------------------------------
    # Run
    # ------------------------------------------------------------------

    @atomic
    def create_run(
        self,
        *,
        run_id: str,
        run_type: RunType,
        project_id: str,
        trigger_source: str,
        config_snapshot_id: str,
        phase: RunPhase = RunPhase.INTAKE,
        status: RunStatus = RunStatus.CREATED,
        parent_run_id: str | None = None,
        baseline_versions: dict[str, str] | None = None,
        actor_id: str = "system",
        actor_type: ActorType = ActorType.SYSTEM,
    ) -> Run:
        if self.store.find_run(run_id) is not None:
            raise TransitionRejected("INVALID_TRANSITION", "Run ID already exists", run_id)
        if phase is not RunPhase.INTAKE or status is not RunStatus.CREATED:
            raise TransitionRejected("INVALID_TRANSITION", "New Run must start at INTAKE/CREATED", run_id)
        run = Run(
            run_id=run_id,
            run_type=run_type,
            parent_run_id=parent_run_id,
            root_run_id=run_id if parent_run_id is None else "",
            project_id=project_id,
            phase=phase,
            status=status,
            state_version=1,
            baseline_versions=baseline_versions or {},
            trigger_source=trigger_source,
            config_snapshot_id=config_snapshot_id,
        )
        if parent_run_id is not None:
            parent = self.store.get_run(parent_run_id)
            if parent.project_id != project_id:
                raise TransitionRejected("GUARD_FAILED", "Cross-project parent Run", run_id)
            run.root_run_id = parent.root_run_id or parent.run_id

        violation = check_composite_guard(run_type, phase, status)
        if violation is not None:
            raise TransitionRejected(
                "INVALID_COMBINATION", violation.message, run_id, current_phase=phase, current_status=status
            )

        self.store.put_run(run)
        self.store.append_event(
            run_id=run_id,
            event_type=EventType.RUN_CREATED,
            actor_id=actor_id,
            actor_type=actor_type,
            payload_ref=f"run_type={run_type.value};phase={phase.value};status={status.value}",
            idempotency_key=f"{run_id}:RUN_CREATED",
        )
        return run

    @atomic
    def transition(
        self,
        run_id: str,
        *,
        target_phase: RunPhase | None = None,
        target_status: RunStatus | None = None,
        expected_version: int | None = None,
        actor_id: str = "system",
        actor_type: ActorType = ActorType.SYSTEM,
        reason: str = "",
    ) -> Run:
        """执行一次受守卫的迁移。

        ``expected_version`` 为 None 时跳过乐观锁检查（仅内部编排使用）；
        外部调用必须传入从 GET /api/runs/{id} 读到的 state_version。
        """
        with self.store.lock():
            current = self.store.get_run(run_id)
            start_version = (
                current.state_version if expected_version is None else expected_version
            )
            current_phase, current_status = current.phase, current.status

            new_phase = target_phase if target_phase is not None else current_phase
            new_status = target_status if target_status is not None else current_status

            self._reject(
                run_id,
                current,
                self._validate(run_id, current_phase, current_status, new_phase, new_status),
            )

            # 乐观锁：CAS 失败抛ConcurrentModificationError，不修改原状态
            updated = current.model_copy(deep=True)
            updated.phase = new_phase
            updated.status = new_status
            updated.state_version = current.state_version + 1
            try:
                self.store.cas_run(updated, start_version)
            except ConcurrentModificationError as exc:
                raise TransitionRejected(
                    "STATE_VERSION_CONFLICT", str(exc), run_id,
                    current_phase=current_phase, current_status=current_status,
                ) from exc

            if new_phase is not current_phase:
                self.store.append_event(
                    run_id=run_id,
                    event_type=EventType.RUN_PHASE_CHANGED,
                    actor_id=actor_id,
                    actor_type=actor_type,
                    payload_ref=f"{current_phase.value}->{new_phase.value};{reason}",
                    idempotency_key=f"{run_id}:PHASE:{current.state_version + 1}",
                )
            if new_status is not current_status:
                self.store.append_event(
                    run_id=run_id,
                    event_type=EventType.RUN_STATUS_CHANGED,
                    actor_id=actor_id,
                    actor_type=actor_type,
                    payload_ref=f"{current_status.value}->{new_status.value};{reason}",
                    idempotency_key=f"{run_id}:STATUS:{current.state_version + 1}",
                )
            return updated

    def _validate(
        self,
        run_id: str,
        current_phase: RunPhase,
        current_status: RunStatus,
        new_phase: RunPhase,
        new_status: RunStatus,
    ) -> str | None:
        """返回拒绝原因；None 表示放行。"""

        from ..contracts.enums import TERMINAL_RUN_STATUSES
        if current_status in TERMINAL_RUN_STATUSES:
            return "Terminal Run cannot be changed"
        phase_changed = new_phase is not current_phase
        status_changed = new_status is not current_status

        # 1) status 白名单
        if status_changed and new_status not in RUN_STATUS_TRANSITIONS[current_status]:
            return (
                f"status 非法跃迁 {current_status.value} -> {new_status.value}；"
                f"允许的目标为 {sorted(s.value for s in RUN_STATUS_TRANSITIONS[current_status])}"
            )

        # 2) phase 白名单（仅在真正换阶段时校验）
        if phase_changed:
            run = self.store.get_run(run_id)
            allowed = allowed_phase_targets(run.run_type, current_phase)
            if new_phase not in allowed:
                table_hint = sorted(p.value for p in allowed) or ["（终态，无出口）"]
                return (
                    f"phase 非法跃迁 {current_phase.value} -> {new_phase.value}；"
                    f"允许的目标为 {table_hint}"
                )

        # 3) 复合守卫：phase 与 status 必须共同通过
        violation = check_composite_guard(
            self.store.get_run(run_id).run_type, new_phase, new_status
        )
        if violation is not None:
            return violation.message

        # 4) 业务组合约束
        guard = self._check_business_guards(run_id, current_phase, new_phase, new_status)
        if guard is not None:
            return guard

        return None

    def _check_business_guards(self, run_id, current_phase, new_phase, new_status):
        from ..contracts.enums import GateId, TERMINAL_RUN_STATUSES
        run = self.store.get_run(run_id)
        changing = current_phase is not new_phase
        if current_phase is RunPhase.G1 and new_phase is RunPhase.ENGINEERING:
            self.require_fresh_passing_gate(run_id, "G1")
        if current_phase is RunPhase.G2 and new_phase is RunPhase.RELEASE_AUTHORIZATION:
            self.require_fresh_passing_gate(run_id, "G1")
            self.require_fresh_passing_gate(run_id, "G2")
        if changing and new_phase is RunPhase.DEPLOYMENT:
            if self.deployment_guard is not None:
                self.deployment_guard(run_id)
            else:
                if not self.allow_simulated_deployment:
                    return "Deployment requires the controlled executor; real deployment is disabled"
                from ..contracts.enums import DeploymentStatus
                from ..runtime.simulation import SimulatedDeployment
                from ..approvals import RBACService
                candidates = [d for d in self.store.deployments_for(run_id)
                              if d.environment_id == "simulation" and d.status is DeploymentStatus.PENDING]
                if len(candidates) != 1:
                    return "Only one pending local simulation is allowed"
                SimulatedDeployment(self.store, self, RBACService(self.store)).validate_authorization(run_id, candidates[0].authorization_id)
        if new_phase is RunPhase.DELIVERY:
            for gate_id in GateId:
                self.require_fresh_passing_gate(run_id, gate_id.value)
        if new_status is RunStatus.NEEDS_RECONCILIATION:
            self.assert_reconciliation_backed(run_id)
        if current_phase is RunPhase.DEPLOYMENT_RECOVERY and changing:
            if run.status is not RunStatus.BLOCKED or self.store.pending_tool_executions(run_id):
                return "Recovery must be verified and BLOCKED before rework"
        if run.status is RunStatus.NEEDS_RECONCILIATION and new_status is not run.status:
            if self.store.pending_tool_executions(run_id):
                return "Unsettled external effects require reconciliation"
        if new_status in {RunStatus.CANCELLED, RunStatus.FAILED} and self.store.pending_tool_executions(run_id):
            return "Cannot terminate with unsettled external effects"
        if new_status is RunStatus.CANCELLED and current_phase is RunPhase.DEPLOYMENT_RECOVERY:
            deployments = [d for d in self.store.deployments_for(run_id) if d.environment_id != "simulation"]
            if not self.store.runtime_get("cancellation", run_id) or any(
                not (self.store.runtime_get("recovery", d.deployment_id) or {}).get("safe") for d in deployments
            ):
                return "Cancelled recovery requires cancellation intent and verified safe environment"
        if new_status is RunStatus.COMPLETED and new_phase not in {
            RunPhase.DELIVERY, RunPhase.MAINTENANCE, RunPhase.INCIDENT, RunPhase.RETROSPECTIVE
        }:
            return "COMPLETED requires the Run's final phase"
        # Any rework invalidates all affected downstream evidence in the same transaction.
        if changing and new_phase in {RunPhase.PRODUCT, RunPhase.ARCHITECTURE, RunPhase.ENGINEERING}:
            affected = {GateId.G2, GateId.G3}
            if new_phase in {RunPhase.PRODUCT, RunPhase.ARCHITECTURE}:
                affected.add(GateId.G1)
            for gate in self.store.gate_results_for(run_id):
                if gate.gate_id in affected and gate.status in {GateStatus.PENDING, GateStatus.PASSED}:
                    self.transition_gate(gate, GateStatus.STALE)
        return None

    def _reject(self, run_id: str, current: Run, reason: str | None) -> None:
        if reason is None:
            return
        code: ErrorCode = (
            "INVALID_COMBINATION" if "组合守卫" in reason else "INVALID_TRANSITION"
        )
        raise TransitionRejected(
            code, reason, run_id, current_phase=current.phase, current_status=current.status
        )

    # ------------------------------------------------------------------
    # 组合守卫所需的跨实体校验
    # ------------------------------------------------------------------

    @atomic
    def advance_to_delivery(self, run_id: str, *, expected_version: int) -> Run:
        """进入 DELIVERY 的前置校验：G1/G2/G3 最新判定均须 PASSED。"""
        from ..contracts.enums import GateId

        run = self.store.get_run(run_id)
        missing = []
        for gate_id in (GateId.G1, GateId.G2, GateId.G3):
            if self.store.latest_passing_gate(run_id, gate_id.value) is None:
                missing.append(gate_id.value)
        if missing:
            raise TransitionRejected(
                "GUARD_FAILED",
                f"缺少有效的门禁通过记录：{missing}；不得标记为 COMPLETED",
                run_id,
                current_phase=run.phase,
                current_status=run.status,
            )
        return self.transition(
            run_id,
            target_phase=RunPhase.DELIVERY,
            target_status=RunStatus.COMPLETED,
            expected_version=expected_version,
            reason="G1/G2/G3 均已 PASSED",
        )

    def assert_reconciliation_backed(self, run_id: str) -> None:
        """NEEDS_RECONCILIATION 必须关联真实未决 ToolExecution。"""
        if not self.store.pending_tool_executions(run_id):
            raise TransitionRejected(
                "GUARD_FAILED",
                "NEEDS_RECONCILIATION 必须关联真实未决的 ToolExecution 或 Deployment，"
                "当前没有",
                run_id,
            )

    # ------------------------------------------------------------------
    # GateResult
    # ------------------------------------------------------------------

    @atomic
    def transition_gate(
        self,
        gate_result: GateResult,
        target: GateStatus,
        *,
        moment: datetime | None = None,
        actor_id: str = "GATE_EVALUATOR",
    ) -> GateResult:
        """GateResult 白名单迁移。只有 GateEvaluator 可写。"""
        if actor_id != "GATE_EVALUATOR":
            raise TransitionRejected(
                "GUARD_FAILED",
                f"只有 GateEvaluator 可写 GateResult，收到 {actor_id}",
                gate_result.run_id,
            )
        current = gate_result.status
        try:
            stored = self.store.get_gate_result(gate_result.gate_result_id)
        except KeyError:
            stored = None
        if stored is not None and stored != gate_result:
            raise TransitionRejected("STATE_VERSION_CONFLICT", "Stale GateResult", gate_result.run_id)
        if target not in GATE_STATUS_TRANSITIONS[current]:
            raise TransitionRejected(
                "INVALID_TRANSITION",
                f"GateResult 非法跃迁 {current.value} -> {target.value}；"
                f"允许的目标为 {sorted(s.value for s in GATE_STATUS_TRANSITIONS[current])}",
                gate_result.run_id,
            )
        updated = gate_result.model_copy(deep=True)
        updated.status = target
        updated.checked_at = moment or utc_now()
        self.store.put_gate_result(updated)
        self.store.append_event(
            run_id=gate_result.run_id,
            event_type=EventType.GATE_RESULT_RECORDED,
            actor_id=actor_id,
            actor_type=ActorType.SYSTEM,
            payload_ref=(
                f"{gate_result.gate_id.value}:{current.value}->{target.value}"
                f";digest={gate_result.input_digest}"
            ),
            idempotency_key=(
                f"{gate_result.run_id}:{gate_result.gate_id.value}:"
                f"{gate_result.gate_result_id}:{target.value}"
            ),
        )
        return updated

    @atomic
    def invalidate_gate(self, gate_result: GateResult, reason: str) -> GateResult:
        """上游产物/审批/策略改变时把旧的PASSED 标记为 STALE，记录保留。"""
        if gate_result.status is not GateStatus.PASSED:
            return gate_result
        updated = gate_result.model_copy(deep=True)
        updated.status = GateStatus.STALE
        updated.checked_at = utc_now()
        self.store.put_gate_result(updated)
        self.store.append_event(
            run_id=gate_result.run_id,
            event_type=EventType.GATE_RESULT_INVALIDATED,
            actor_id="system",
            actor_type=ActorType.SYSTEM,
            payload_ref=f"{gate_result.gate_id.value}:PASSED->STALE;{reason}",
            idempotency_key=(
                f"{gate_result.run_id}:{gate_result.gate_id.value}:"
                f"{gate_result.gate_result_id}:STALE"
            ),
        )
        return updated

    def require_fresh_passing_gate(self, run_id: str, gate_id: str, *, now=None) -> GateResult:
        """研发/部署前必须检查最新判定是 PASSED。"""
        latest = self.store.latest_gate_result(run_id, gate_id)
        if latest is None:
            raise TransitionRejected(
                "GUARD_FAILED", f"{gate_id} 从未评估", run_id
            )
        if latest.status is not GateStatus.PASSED:
            raise TransitionRejected(
                "GUARD_FAILED",
                f"{gate_id} 最新判定为 {latest.status.value}，不是 PASSED",
                run_id,
            )
        if gate_id == "G1":
            from ..approvals import ApprovalRequestService, RBACService, compute_input_digest
            run = self.store.get_run(run_id)
            expected = compute_input_digest(run.baseline_versions.get("spec", ""),
                                            run.baseline_versions.get("architecture", ""))
            if latest.input_digest != expected:
                raise TransitionRejected("GUARD_FAILED", "G1 基线已失效", run_id)
            approvals = ApprovalRequestService(self.store, RBACService(self.store))
            for approval_id in latest.approval_ids:
                try:
                    approval = self.store.get_approval_request(approval_id)
                except KeyError as exc:
                    raise TransitionRejected("GUARD_FAILED", "G1 审批记录缺失", run_id) from exc
                if (approval.run_id != run_id or approval.input_digest != expected
                        or not approvals.is_effective(approval, now=now)):
                    raise TransitionRejected("GUARD_FAILED", "G1 审批或审批人权限已失效", run_id)
        if gate_id == "G2":
            from ..approvals.waivers import waiver_effective
            from ..approvals import RBACService
            waivers = self.store.runtime_get("gate_waivers", latest.gate_result_id) or {"ids": []}
            for waiver_id in waivers["ids"]:
                if not waiver_effective(self.store, RBACService(self.store), self.store.get_risk_waiver(waiver_id), now or utc_now()):
                    raise TransitionRejected("GUARD_FAILED", "G2 风险豁免已失效", run_id)
            from ..contracts.enums import HARD_BLOCKING_SEVERITIES
            if self.store.open_issues_by_severity(run_id, HARD_BLOCKING_SEVERITIES):
                raise TransitionRejected("GUARD_FAILED", "G2 存在未解决的严重问题", run_id)
            if latest.commit_sha is not None:
                if latest.commit_sha != self.store.get_run(run_id).baseline_versions.get("commit"):
                    raise TransitionRejected("GUARD_FAILED", "G2 Commit 已失效", run_id)
        return latest
