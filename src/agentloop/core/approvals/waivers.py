"""风险豁免生命周期。严重度取自 Issue，不能由申请方调低。"""
from datetime import timedelta
from uuid import uuid4
from ..contracts.enums import HARD_BLOCKING_SEVERITIES, RiskWaiverStatus, GateId, Severity
from ..contracts.models import RiskWaiver, utc_now
from ..orchestration.store import atomic
from ..runtime.configuration import digest
from .rbac import AccessDenied


def waiver_effective(store, rbac, waiver, moment):
    run = store.get_run(waiver.run_id)
    if not waiver.is_active_at(moment) or waiver.expires_at is None or waiver.input_digest != digest(run.baseline_versions):
        return False
    try:
        rbac.require_human(waiver.approved_by)
        if "security_reviewer" not in rbac.roles_of(waiver.approved_by, run.project_id, moment): return False
        return all(store.get_issue(issue_id).run_id == run.run_id and store.get_issue(issue_id).severity not in HARD_BLOCKING_SEVERITIES for issue_id in waiver.issue_ids)
    except (KeyError, PermissionError, ValueError, AccessDenied):
        return False


class RiskWaiverService:
    def __init__(self, repository, rbac, transitions):
        self.repo, self.store, self.rbac, self.transitions = repository, repository.store, rbac, transitions

    @atomic
    def request(self, run_id, *, principal_id, issue_ids, rationale, controls, hours=24):
        run = self.store.get_run(run_id)
        self.rbac.require_human(principal_id); self.rbac.assert_project_access(principal_id, run.project_id)
        if not issue_ids or not rationale.strip() or not controls.strip() or not 0 < hours <= 24:
            raise ValueError("豁免需要问题、理由、补偿控制和不超过24小时的有效期")
        issues = [self.store.get_issue(key) for key in issue_ids]
        if any(issue.run_id != run_id for issue in issues): raise PermissionError("跨 Run 豁免被拒绝")
        levels = list(Severity)
        severity = min((issue.severity for issue in issues), key=levels.index)
        waiver = RiskWaiver(waiver_id="waiver-"+uuid4().hex, run_id=run_id, issue_ids=issue_ids, severity=severity,
            rationale=rationale, controls=controls, scope=run.project_id, input_digest=digest(run.baseline_versions),
            policy_version="risk-waiver-v1.2", requested_by=principal_id, expires_at=utc_now()+timedelta(hours=hours))
        self.store.put_risk_waiver(waiver); self.repo.audit(run_id,"RISK_WAIVER_REQUESTED",waiver.model_dump(mode="json"))
        return waiver

    @atomic
    def decide(self, waiver_id, *, principal_id, approve, reason=""):
        waiver = self.store.get_risk_waiver(waiver_id); run = self.store.get_run(waiver.run_id)
        self.rbac.require_human(principal_id); self.rbac.require_role(principal_id,"security_reviewer",run.project_id)
        if waiver.input_digest != digest(run.baseline_versions): raise ValueError("豁免基线已改变")
        if approve and any(self.store.get_issue(key).severity in HARD_BLOCKING_SEVERITIES for key in waiver.issue_ids):
            raise ValueError("P1/严重漏洞不可豁免")
        waiver.decide(approve,principal_id,utc_now(),reason)
        self.store.put_risk_waiver(waiver); self.repo.audit(run.run_id,"RISK_WAIVER_DECIDED",waiver.model_dump(mode="json"))
        return waiver

    @atomic
    def revoke(self, waiver_id, *, principal_id):
        waiver = self.store.get_risk_waiver(waiver_id); run=self.store.get_run(waiver.run_id)
        self.rbac.require_human(principal_id); self.rbac.require_role(principal_id,"security_reviewer",run.project_id)
        waiver.status=RiskWaiverStatus.REVOKED; self.store.put_risk_waiver(waiver)
        from ..contracts.enums import GateStatus
        for gate in self.store.gate_results_for(run.run_id):
            if gate.gate_id in {GateId.G2,GateId.G3} and gate.status in {GateStatus.PASSED,GateStatus.PENDING}:
                self.transitions.transition_gate(gate,GateStatus.STALE)
        self.repo.audit(run.run_id,"RISK_WAIVER_REVOKED",{"waiver_id":waiver_id,"principal_id":principal_id})
