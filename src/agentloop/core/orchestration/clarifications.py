"""澄清请求、版本绑定、真人答复与幂等恢复。"""

import json
from uuid import uuid5, NAMESPACE_URL

from ..contracts.enums import ActorType, ClarificationStatus, EventType, RunStatus
from ..contracts.models import ClarificationRequest, digest_of, utc_now
from .store import atomic


def clarification_digest(run):
    return digest_of(json.dumps({"phase": run.phase.value, "baseline": run.baseline_versions}, sort_keys=True))


class ClarificationService:
    def __init__(self, store, transitions, rbac):
        self.store, self.transitions, self.rbac = store, transitions, rbac

    @atomic
    def ensure(self, *, run_id, question, kind, required_role="project_owner", now=None):
        run = self.store.get_run(run_id)
        digest = clarification_digest(run)
        question_id = "q-" + uuid5(NAMESPACE_URL, f"{run_id}:{digest}:{question}:{kind}").hex
        try:
            return self.store.get_clarification(question_id)
        except KeyError:
            pass
        if run.status not in {RunStatus.RUNNING, RunStatus.WAITING_GATE, RunStatus.WAITING_APPROVAL,
                              RunStatus.PAUSED_FOR_HUMAN, RunStatus.BLOCKED}:
            raise ValueError("当前 Run 不允许创建澄清请求")
        pending = [q for q in self.store.clarifications_for(run_id) if q.status is ClarificationStatus.OPEN]
        resume_status = run.status
        if run.status is RunStatus.PAUSED_FOR_HUMAN:
            resume_status = pending[0].resume_status if pending else RunStatus.RUNNING
        request = ClarificationRequest(
            question_id=question_id, run_id=run_id, phase=run.phase, kind=kind,
            question=question, required_role=required_role, input_digest=digest,
            resume_status=resume_status,
            created_at=now or utc_now(),
        )
        self.store.put_clarification(request)
        if run.status is not RunStatus.PAUSED_FOR_HUMAN:
            self.transitions.transition(run_id, target_status=RunStatus.PAUSED_FOR_HUMAN,
                                        expected_version=run.state_version)
        self.store.append_event(
            run_id=run_id, event_type=EventType.CLARIFICATION_REQUESTED,
            actor_id="orchestrator", actor_type=ActorType.SYSTEM,
            payload_ref=request.model_dump_json(), idempotency_key=f"{question_id}:REQUESTED",
        )
        return request

    @atomic
    def answer(self, *, question_id, principal_id, answer, expected_version, now=None):
        moment = now or utc_now()
        request = self.store.get_clarification(question_id)
        run = self.store.get_run(request.run_id)
        self.rbac.require_human(principal_id)
        self.rbac.assert_project_access(principal_id, run.project_id, moment)
        if request.required_role not in self.rbac.roles_of(principal_id, run.project_id, moment):
            raise PermissionError("缺少澄清答复角色")
        if request.input_digest != clarification_digest(run):
            raise ValueError("澄清所依据的输入已变更")
        if request.status is ClarificationStatus.ANSWERED:
            if (request.answer, request.answered_by) != (answer, principal_id):
                raise ValueError("已经答复，不允许覆盖")
            return request
        request.validate_answer(answer, moment)
        if run.status is not RunStatus.PAUSED_FOR_HUMAN:
            raise ValueError("Run 未暂停等待澄清")
        request.status, request.answer, request.answered_by = ClarificationStatus.ANSWERED, answer, principal_id
        self.store.put_clarification(request)
        open_requests = [q for q in self.store.clarifications_for(run.run_id) if q.status is ClarificationStatus.OPEN]
        if not open_requests:
            self.transitions.transition(run.run_id, target_status=request.resume_status,
                                        expected_version=expected_version)
        elif run.state_version != expected_version:
            raise ValueError("state_version 冲突")
        self.store.append_event(
            run_id=run.run_id, event_type=EventType.CLARIFICATION_ANSWERED,
            actor_id=principal_id, actor_type=ActorType.HUMAN,
            payload_ref=request.model_dump_json(), idempotency_key=f"{question_id}:ANSWERED",
        )
        return request
