"""可替换仓储与事务接口；内存用于单元测试，SQLite 用于本地持久执行。"""

from __future__ import annotations

import threading
import copy
from contextlib import contextmanager
from functools import wraps
from uuid import uuid4
from collections.abc import Iterable

from ..contracts.enums import ActorType, EventType, GateStatus
from ..contracts.knowledge import EvolutionProposal, MemoryProposal, MemoryRecord
from ..contracts.models import (
    ApprovalRequest,
    Artifact,
    Deployment,
    Principal,
    RoleBinding,
    ClarificationRequest,
    ExecutionEvent,
    GateResult,
    Issue,
    Release,
    ReleaseAuthorization,
    ReleaseAuthorizationRequest,
    RiskWaiver,
    Run,
    ToolExecution,
    utc_now,
)


class ConcurrentModificationError(RuntimeError):
    """state_version 乐观锁冲突。对应 API 层的 409。"""


def detached(method):
    @wraps(method)
    def wrapped(*args, **kwargs):
        return copy.deepcopy(method(*args, **kwargs))
    return wrapped


def atomic(method):
    @wraps(method)
    def wrapped(self, *args, **kwargs):
        with self.store.transaction():
            return method(self, *args, **kwargs)
    return wrapped


class InMemoryStore:
    """线程安全的内存存储。所有写操作在单个锁内完成，保证事务性。"""

    def __init__(self) -> None:
        self._lock = threading.RLock()
        self._runs: dict[str, Run] = {}
        self._events: list[ExecutionEvent] = []
        self._gate_results: dict[str, GateResult] = {}
        self._issues: dict[str, Issue] = {}
        self._artifacts: dict[str, Artifact] = {}
        self._clarifications: dict[str, ClarificationRequest] = {}
        self._approval_requests: dict[str, ApprovalRequest] = {}
        self._risk_waivers: dict[str, RiskWaiver] = {}
        self._tool_executions: dict[str, ToolExecution] = {}
        self._releases: dict[str, Release] = {}
        self._authorization_requests: dict[str, ReleaseAuthorizationRequest] = {}
        self._authorizations: dict[str, ReleaseAuthorization] = {}
        self._event_keys: set[str] = set()
        self._sequence = 0
        self._deployments = {}
        self._principals = {}
        self._bindings = {}
        self._memory_proposals: dict[str, MemoryProposal] = {}
        self._memories: dict[str, MemoryRecord] = {}
        self._evolution_proposals: dict[str, EvolutionProposal] = {}
        self._runtime_records = {}

    def runtime_get(self, namespace, key):
        with self._lock:
            record = self._runtime_records.get(f"{namespace}:{key}")
            return copy.deepcopy(record.data) if record else None

    def runtime_put(self, namespace, key, data):
        from ..contracts.phase2 import RuntimeRecord
        with self._lock:
            self._runtime_records[f"{namespace}:{key}"] = RuntimeRecord(data=copy.deepcopy(data))

    def runtime_list(self, namespace):
        with self._lock:
            return [copy.deepcopy(v.data) for k, v in self._runtime_records.items() if k.startswith(namespace + ":")]

    @contextmanager
    def transaction(self):
        """服务方法的状态和事件一起回滚，嵌套事务也适用。"""
        with self._lock:
            before = copy.deepcopy({k: v for k, v in vars(self).items() if k != "_lock"})
            try:
                yield
            except BaseException:
                for key, value in before.items():
                    setattr(self, key, value)
                raise

    # ---------------- 事件 ----------------

    def append_event(
        self,
        *,
        run_id: str,
        event_type: EventType,
        actor_id: str,
        actor_type: ActorType,
        payload_ref: str,
        idempotency_key: str,
    ) -> ExecutionEvent:
        """追加事件。相同 idempotency_key 不产生第二条记录。"""
        with self._lock:
            if idempotency_key in self._event_keys:
                existing = next(
                    e for e in self._events if e.idempotency_key == idempotency_key
                )
                if (existing.run_id, existing.type, existing.actor_id, existing.actor_type, existing.payload_ref) != (
                    run_id, event_type, actor_id, actor_type, payload_ref
                ):
                    raise ValueError("Idempotency key collision")
                return existing.model_copy(deep=True)
            self._sequence += 1
            event = ExecutionEvent(
                event_id=f"evt-{uuid4().hex}",
                run_id=run_id,
                type=event_type,
                actor_id=actor_id,
                actor_type=actor_type,
                timestamp=utc_now(),
                payload_ref=payload_ref,
                idempotency_key=idempotency_key,
                sequence=self._sequence,
            )
            self._events.append(event)
            self._event_keys.add(idempotency_key)
            return event.model_copy(deep=True)

    @detached
    def events_for(self, run_id: str) -> list[ExecutionEvent]:
        with self._lock:
            return sorted(
                (e for e in self._events if e.run_id == run_id), key=lambda e: e.sequence
            )

    def all_events(self) -> list[ExecutionEvent]:
        with self._lock:
            return copy.deepcopy(self._events)

    def count_events_of_type(self, event_type: EventType, run_id: str | None = None) -> int:
        with self._lock:
            return len(
                [
                    e
                    for e in self._events
                    if e.type is event_type and (run_id is None or e.run_id == run_id)
                ]
            )

    # ---------------- Run ----------------

    def put_run(self, run: Run) -> None:
        with self._lock:
            self._runs[run.run_id] = run.model_copy(deep=True)

    def get_run(self, run_id: str) -> Run:
        with self._lock:
            if run_id not in self._runs:
                raise KeyError(f"run {run_id} 不存在")
            return self._runs[run_id].model_copy(deep=True)

    def find_run(self, run_id: str) -> Run | None:
        with self._lock:
            return self.get_run(run_id) if run_id in self._runs else None

    def list_runs(self, project_id: str | None = None) -> list[Run]:
        with self._lock:
            runs = list(self._runs.values())
            if project_id is not None:
                runs = [r for r in runs if r.project_id == project_id]
            return copy.deepcopy(runs)

    def cas_run(self, run: Run, expected_version: int) -> None:
        """乐观锁写入。state_version 不符即拒绝，不做部分落库。"""
        with self.transaction():
            current = self._runs.get(run.run_id)
            if current is None:
                raise KeyError(f"run {run.run_id} 不存在")
            if current.state_version != expected_version:
                raise ConcurrentModificationError(
                    f"run {run.run_id} state_version 冲突："
                    f"期望 {expected_version}，实际 {current.state_version}"
                )
            self._runs[run.run_id] = run.model_copy(deep=True)

    # ---------------- GateResult ----------------

    def put_gate_result(self, result: GateResult) -> None:
        with self._lock:
            self._gate_results[result.gate_result_id] = result.model_copy(deep=True)

    def get_gate_result(self, gate_result_id: str) -> GateResult:
        with self._lock:
            if gate_result_id not in self._gate_results:
                raise KeyError(f"gate_result {gate_result_id} 不存在")
            return self._gate_results[gate_result_id].model_copy(deep=True)

    def gate_results_for(self, run_id: str, gate_id: str | None = None) -> list[GateResult]:
        with self._lock:
            results = [g for g in self._gate_results.values() if g.run_id == run_id]
            if gate_id is not None:
                results = [g for g in results if g.gate_id.value == gate_id]
            return copy.deepcopy(results)

    def latest_gate_result(self, run_id: str, gate_id: str) -> GateResult | None:
        results = self.gate_results_for(run_id, gate_id)
        return results[-1] if results else None

    def latest_passing_gate(self, run_id: str, gate_id: str) -> GateResult | None:
        """最近一条有效通过记录。STALE / REJECTED 不算通过。"""
        latest = self.latest_gate_result(run_id, gate_id)
        return latest if latest and latest.status is GateStatus.PASSED else None

    @detached
    def find_gate_by_idempotency(
        self, run_id: str, gate_id: str, input_digest: str, policy_version: str,
        deployment_id: str | None = None,
    ) -> GateResult | None:
        """同 gate_id、同输入摘要、同策略版本的评估是幂等的。"""
        with self._lock:
            for result in self._gate_results.values():
                if (
                    result.run_id == run_id
                    and result.gate_id.value == gate_id
                    and result.input_digest == input_digest
                    and result.policy_version == policy_version
                    and result.deployment_id == deployment_id
                    and result.status in (GateStatus.PENDING, GateStatus.PASSED)
                ):
                    return result
            return None

    # ---------------- Issue ----------------

    def put_issue(self, issue: Issue) -> None:
        with self._lock:
            self._issues[issue.issue_id] = issue.model_copy(deep=True)

    def get_issue(self, issue_id: str) -> Issue:
        with self._lock:
            if issue_id not in self._issues:
                raise KeyError(f"issue {issue_id} 不存在")
            return self._issues[issue_id].model_copy(deep=True)

    def list_issues(self, run_id: str | None = None) -> list[Issue]:
        with self._lock:
            issues = list(self._issues.values())
            if run_id is not None:
                issues = [i for i in issues if i.run_id == run_id]
            return copy.deepcopy(issues)

    def open_issues_by_severity(self, run_id: str, severities: Iterable) -> list[Issue]:
        wanted = set(severities)
        from ..contracts.enums import IssueStatus

        return [
            i
            for i in self.list_issues(run_id)
            if i.severity in wanted and i.status is not IssueStatus.RESOLVED
        ]

    # ---------------- Artifact ----------------

    def put_artifact(self, artifact: Artifact) -> None:
        with self.transaction():
            if artifact.artifact_id in self._artifacts and self._artifacts[artifact.artifact_id] != artifact:
                raise ValueError("Artifact cannot be overwritten")
            self._artifacts[artifact.artifact_id] = artifact.model_copy(deep=True)

    def get_artifact(self, artifact_id: str) -> Artifact:
        with self._lock:
            if artifact_id not in self._artifacts:
                raise KeyError(f"artifact {artifact_id} 不存在")
            return self._artifacts[artifact_id].model_copy(deep=True)

    @detached
    def artifacts_for(self, run_id: str) -> list[Artifact]:
        with self._lock:
            return [a for a in self._artifacts.values() if a.run_id == run_id]

    # ---------------- Phase 4 知识库 ----------------

    def put_memory_proposal(self, proposal: MemoryProposal) -> None:
        with self._lock:
            self._memory_proposals[proposal.proposal_id] = proposal.model_copy(deep=True)

    def get_memory_proposal(self, proposal_id: str) -> MemoryProposal:
        with self._lock:
            if proposal_id not in self._memory_proposals:
                raise KeyError(f"memory_proposal {proposal_id} 不存在")
            return self._memory_proposals[proposal_id].model_copy(deep=True)

    @detached
    def memory_proposals_for(self, run_id: str | None = None) -> list[MemoryProposal]:
        with self._lock:
            proposals = list(self._memory_proposals.values())
            if run_id is not None:
                proposals = [p for p in proposals if p.run_id == run_id]
            return proposals

    def put_memory(self, record: MemoryRecord) -> None:
        with self._lock:
            self._memories[record.memory_id] = record.model_copy(deep=True)

    def get_memory(self, memory_id: str) -> MemoryRecord:
        with self._lock:
            if memory_id not in self._memories:
                raise KeyError(f"memory {memory_id} 不存在")
            return self._memories[memory_id].model_copy(deep=True)

    @detached
    def memories(self) -> list[MemoryRecord]:
        with self._lock:
            return list(self._memories.values())

    def put_evolution_proposal(self, proposal: EvolutionProposal) -> None:
        with self._lock:
            self._evolution_proposals[proposal.proposal_id] = proposal.model_copy(deep=True)

    def get_evolution_proposal(self, proposal_id: str) -> EvolutionProposal:
        with self._lock:
            if proposal_id not in self._evolution_proposals:
                raise KeyError(f"evolution_proposal {proposal_id} 不存在")
            return self._evolution_proposals[proposal_id].model_copy(deep=True)

    @detached
    def evolution_proposals_for(self, run_id: str | None = None) -> list[EvolutionProposal]:
        with self._lock:
            proposals = list(self._evolution_proposals.values())
            if run_id is not None:
                proposals = [p for p in proposals if p.run_id == run_id]
            return proposals

    # ---------------- Clarification ----------------

    def put_clarification(self, request: ClarificationRequest) -> None:
        with self._lock:
            self._clarifications[request.question_id] = request.model_copy(deep=True)

    def get_clarification(self, question_id: str) -> ClarificationRequest:
        with self._lock:
            if question_id not in self._clarifications:
                raise KeyError(f"question {question_id} 不存在")
            return self._clarifications[question_id].model_copy(deep=True)

    @detached
    def clarifications_for(self, run_id: str) -> list[ClarificationRequest]:
        with self._lock:
            return [
                c for c in self._clarifications.values() if c.run_id == run_id
            ]

    # ---------------- G1 审批请求 ----------------

    def put_approval_request(self, request: ApprovalRequest) -> None:
        with self._lock:
            self._approval_requests[request.approval_id] = request.model_copy(deep=True)

    def get_approval_request(self, approval_id: str) -> ApprovalRequest:
        with self._lock:
            if approval_id not in self._approval_requests:
                raise KeyError(f"approval {approval_id} 不存在")
            return self._approval_requests[approval_id].model_copy(deep=True)

    @detached
    def approval_requests_for(self, run_id: str) -> list[ApprovalRequest]:
        with self._lock:
            return [r for r in self._approval_requests.values() if r.run_id == run_id]

    # ---------------- 风险豁免 ----------------

    def put_risk_waiver(self, waiver: RiskWaiver) -> None:
        with self._lock:
            self._risk_waivers[waiver.waiver_id] = waiver.model_copy(deep=True)

    def get_risk_waiver(self, waiver_id: str) -> RiskWaiver:
        with self._lock:
            if waiver_id not in self._risk_waivers:
                raise KeyError(f"risk_waiver {waiver_id} 不存在")
            return self._risk_waivers[waiver_id].model_copy(deep=True)

    def active_waiver_ids(self, run_id: str, moment=None) -> list[str]:
        from ..contracts.enums import RiskWaiverStatus

        moment = moment or utc_now()
        with self._lock:
            return [
                issue_id
                for w in self._risk_waivers.values()
                if w.run_id == run_id
                and w.status is RiskWaiverStatus.ACTIVE
                and (w.expires_at is None or w.expires_at >= moment)
                for issue_id in w.issue_ids
            ]

    # ---------------- 副作用 ----------------

    def put_tool_execution(self, execution: ToolExecution) -> None:
        with self._lock:
            self._tool_executions[execution.invocation_id] = execution.model_copy(deep=True)

    def get_tool_execution(self, invocation_id: str) -> ToolExecution:
        with self._lock:
            if invocation_id not in self._tool_executions:
                raise KeyError(f"tool_execution {invocation_id} 不存在")
            return self._tool_executions[invocation_id].model_copy(deep=True)

    @detached
    def find_tool_execution_by_key(self, idempotency_key: str) -> ToolExecution | None:
        """重启恢复执行前必须先读历史，判断是否需要补发。"""
        with self._lock:
            for execution in self._tool_executions.values():
                if execution.idempotency_key == idempotency_key:
                    return execution
            return None

    @detached
    def pending_tool_executions(self, run_id: str) -> list[ToolExecution]:
        """未结算的副作用：NEEDS_RECONCILIATION 必须关联其中之一。"""
        from ..contracts.enums import ToolExecutionStatus

        unsettled = {
            ToolExecutionStatus.STARTED,
            ToolExecutionStatus.PARTIALLY_COMMITTED,
            ToolExecutionStatus.UNKNOWN,
        }
        with self._lock:
            return [
                t
                for t in self._tool_executions.values()
                if t.run_id == run_id and t.status in unsettled
            ]

    # ---------------- 发布 ----------------

    def put_release(self, release: Release) -> None:
        with self._lock:
            self._releases[release.release_id] = release.model_copy(deep=True)

    def get_release(self, release_id: str) -> Release:
        with self._lock:
            if release_id not in self._releases:
                raise KeyError(f"release {release_id} 不存在")
            return self._releases[release_id].model_copy(deep=True)

    @detached
    def releases_for(self, run_id: str) -> list[Release]:
        with self._lock:
            return [r for r in self._releases.values() if r.run_id == run_id]

    def put_authorization_request(self, request: ReleaseAuthorizationRequest) -> None:
        with self._lock:
            self._authorization_requests[request.authorization_request_id] = request.model_copy(deep=True)

    def get_authorization_request(self, request_id: str) -> ReleaseAuthorizationRequest:
        with self._lock:
            if request_id not in self._authorization_requests:
                raise KeyError(f"authorization_request {request_id} 不存在")
            return self._authorization_requests[request_id].model_copy(deep=True)

    def find_authorization_request_idempotent(
        self,
        release_id: str,
        environment_id: str,
        targets_digest: str,
        request_version: int,
    ) -> ReleaseAuthorizationRequest | None:
        with self._lock:
            for request in self._authorization_requests.values():
                if (
                    request.release_id == release_id
                    and request.environment_id == environment_id
                    and request.targets_digest() == targets_digest
                    and request.request_version == request_version
                ):
                    return request
            return None

    def put_authorization(self, authorization: ReleaseAuthorization) -> None:
        with self._lock:
            self._authorizations[authorization.authorization_id] = authorization.model_copy(deep=True)

    def get_authorization(self, authorization_id: str) -> ReleaseAuthorization:
        with self._lock:
            if authorization_id not in self._authorizations:
                raise KeyError(f"authorization {authorization_id} 不存在")
            return self._authorizations[authorization_id].model_copy(deep=True)

    def authorization_requests_for(self, run_id: str):
        with self._lock:
            release_ids = {r.release_id for r in self.releases_for(run_id)}
            return [r.model_copy(deep=True) for r in self._authorization_requests.values() if r.release_id in release_ids]

    def authorizations_for(self, run_id: str):
        with self._lock:
            release_ids = {r.release_id for r in self.releases_for(run_id)}
            return [r.model_copy(deep=True) for r in self._authorizations.values() if r.release_id in release_ids]

    def lock(self) -> threading.RLock:
        """供需要跨多次存储操作保持原子的服务使用。"""
        return self.transaction()

    def put_deployment(self, deployment: Deployment):
        with self._lock:
            self._deployments[deployment.deployment_id] = deployment.model_copy(deep=True)

    def get_deployment(self, deployment_id: str) -> Deployment:
        with self._lock:
            return self._deployments[deployment_id].model_copy(deep=True)

    def deployments_for(self, run_id: str):
        with self._lock:
            return [d.model_copy(deep=True) for d in self._deployments.values() if d.run_id == run_id]

    def put_principal(self, principal: Principal):
        with self._lock:
            self._principals[principal.principal_id] = principal.model_copy(deep=True)

    def get_principal(self, principal_id: str) -> Principal:
        with self._lock:
            return self._principals[principal_id].model_copy(deep=True)

    def put_role_binding(self, binding: RoleBinding):
        with self._lock:
            self._bindings[binding.binding_id] = binding.model_copy(deep=True)

    def role_bindings(self):
        with self._lock:
            return [b.model_copy(deep=True) for b in self._bindings.values()]
