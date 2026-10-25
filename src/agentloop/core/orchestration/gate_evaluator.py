"""确定性 G1/G2/G3 门禁。输入只由可信编排层根据归档证据构造。"""

from datetime import timedelta
from uuid import uuid4

from ..contracts.enums import (
    ApprovalDecision, ApprovalSubjectType, DeploymentStatus, GateId, GateStatus,
    HARD_BLOCKING_SEVERITIES, HumanApprovalMode, RunPhase, RunStatus,
)
from ..contracts.models import GateResult, utc_now
from ..approvals.approval_requests import compute_input_digest
from .store import atomic

GATE_POLICY_VERSION = "gate-policy-v1.2"


def request_human_approval_policy():
    return {
        "spec": HumanApprovalMode.OPTIONAL,
        "architecture": HumanApprovalMode.OPTIONAL,
        "force_required_if": ["new_external_api", "irreversible_data_migration", "high_business_impact"],
        "reviewer_role": ["project_owner", "product_approver"],
        "expires_after_hours": 72,
    }


class GateEvaluator:
    def __init__(self, store, transitions, approvals, *, policy_version=GATE_POLICY_VERSION,
                 human_approval_policy=None, archive=None):
        self.store, self.transitions, self.approvals = store, transitions, approvals
        self.policy_version = policy_version
        self.archive = archive
        self.human_policy = request_human_approval_policy()
        self.human_policy.update(human_approval_policy or {})
        for subject in ("spec", "architecture"):
            self.human_policy[subject] = HumanApprovalMode(self.human_policy[subject])

    @atomic
    def evaluate(self, request, *, actor_id="GATE_EVALUATOR", now=None):
        if actor_id != "GATE_EVALUATOR":
            raise PermissionError("只能由服务端 GateEvaluator 评估门禁")
        moment = now or utc_now()
        run = self.store.get_run(request.run_id)
        if request.policy_version != self.policy_version:
            raise ValueError("门禁策略版本不匹配")
        if run.phase.value != request.gate_id.value or run.status not in {
            RunStatus.RUNNING, RunStatus.WAITING_GATE, RunStatus.WAITING_APPROVAL
        }:
            raise ValueError("Run 未在可评估的门禁阶段")
        blockers = self._blockers(request, moment)
        approval_ids = []
        waiting = False
        if request.gate_id is GateId.G1 and not blockers:
            forced = bool(set(request.risk_triggers) & set(self.human_policy["force_required_if"]))
            for subject in ApprovalSubjectType:
                mode = self.human_policy[subject.value.lower()]
                if not (forced or mode is HumanApprovalMode.REQUIRED or (
                    mode is HumanApprovalMode.OPTIONAL and request.user_requested_extra_confirmation
                )):
                    continue
                approval, _ = self.approvals.ensure_required(
                    run_id=run.run_id, subject_type=subject, input_digest=request.input_digest,
                    required_roles=list(self.human_policy["reviewer_role"]), request_version=1,
                    expires_in_hours=self.human_policy["expires_after_hours"],
                    actor_id=actor_id, now=moment,
                )
                approval_ids.append(approval.approval_id)
                if approval.revoked or approval.expires_at <= moment or approval.decision is ApprovalDecision.REJECT:
                    blockers.append(f"APPROVAL_INVALID:{approval.approval_id}")
                elif approval.decision is ApprovalDecision.APPROVE and not self.approvals.is_effective(approval, now=moment):
                    blockers.append(f"APPROVAL_IDENTITY_INVALID:{approval.approval_id}")
                elif not self.approvals.is_effective(approval, now=moment):
                    waiting = True

        existing = self.store.find_gate_by_idempotency(
            run.run_id, request.gate_id.value, request.input_digest, self.policy_version,
            request.deployment_id,
        )
        if existing and existing.status is GateStatus.PASSED:
            if not blockers and not waiting and existing.approval_ids == approval_ids:
                return existing
            self.transitions.transition_gate(existing, GateStatus.STALE, moment=moment)
            existing = None
        result = existing
        if result is None:
            result = GateResult(
                gate_result_id=f"gate-{uuid4().hex}", run_id=run.run_id,
                gate_id=request.gate_id, policy_version=self.policy_version,
                input_digest=request.input_digest, deployment_id=request.deployment_id,
                commit_sha=run.baseline_versions.get("commit") if request.gate_id is GateId.G2 else None,
                evidence_artifact_id=request.evidence_artifact_id,
            )
            result = self.transitions.transition_gate(result, GateStatus.PENDING, moment=moment)
        result.blocker_issue_ids = blockers
        result.approval_ids = approval_ids
        if request.gate_id is GateId.G2 and request.active_waiver_ids:
            self.store.runtime_put("gate_waivers", result.gate_result_id, {"ids": request.active_waiver_ids})
        # 先持久化完整证据元数据，再由受控状态服务迁移，避免陈旧对象覆盖。
        self.store.put_gate_result(result)
        target = GateStatus.REJECTED if blockers else (GateStatus.PENDING if waiting else GateStatus.PASSED)
        if target is not GateStatus.PENDING:
            result = self.transitions.transition_gate(result, target, moment=moment)
        if waiting and not blockers and run.status is not RunStatus.WAITING_APPROVAL:
            self.transitions.transition(run.run_id, target_status=RunStatus.WAITING_APPROVAL,
                                        expected_version=run.state_version)
        if blockers and request.gate_id is GateId.G3:
            self.transitions.transition(run.run_id, target_phase=RunPhase.DEPLOYMENT_RECOVERY,
                                        target_status=RunStatus.RUNNING, expected_version=run.state_version)
        elif blockers and run.status is not RunStatus.BLOCKED:
            self.transitions.transition(run.run_id, target_status=RunStatus.BLOCKED,
                                        expected_version=run.state_version)
        return result

    def _blockers(self, request, moment):
        run = self.store.get_run(request.run_id)
        blockers = []
        if request.gate_id is GateId.G1:
            expected = compute_input_digest(run.baseline_versions.get("spec", ""),
                                            run.baseline_versions.get("architecture", ""))
            if (not request.spec_digest or not request.architecture_digest
                    or request.spec_digest != run.baseline_versions.get("spec")
                    or request.architecture_digest != run.baseline_versions.get("architecture")
                    or request.input_digest != expected):
                blockers.append("BASELINE_MISMATCH_OR_MISSING")
            for field in ("product_leader_accepted", "product_audit_passed", "architecture_review_passed"):
                if getattr(request, field) is not True:
                    blockers.append(field.upper())
        elif request.gate_id is GateId.G2:
            self.transitions.require_fresh_passing_gate(run.run_id, "G1", now=moment)
            for field in ("engineering_leader_accepted", "required_tests_complete"):
                if getattr(request, field) is not True:
                    blockers.append(field.upper())
            blockers.extend(f"UNRESOLVED:{i.issue_id}" for i in
                            self.store.open_issues_by_severity(run.run_id, HARD_BLOCKING_SEVERITIES))
            from ..approvals.waivers import waiver_effective
            from ..approvals import RBACService
            for waiver_id in request.active_waiver_ids:
                try:
                    waiver = self.store.get_risk_waiver(waiver_id)
                    if waiver.run_id != run.run_id or not waiver_effective(self.store, RBACService(self.store), waiver, moment):
                        blockers.append("RISK_WAIVER_INVALID")
                except KeyError:
                    blockers.append("RISK_WAIVER_MISSING")
            if run.baseline_versions.get("commit") and not request.evidence_artifact_id:
                blockers.append("DELIVERY_EVIDENCE_REQUIRED")
            if request.evidence_artifact_id:
                try:
                    blockers.extend(self._verify_delivery_evidence(request, run))
                except (KeyError, TypeError, ValueError, PermissionError, OSError):
                    blockers.append("DELIVERY_EVIDENCE_UNREADABLE_OR_INVALID")
        else:
            from .state_transition import TransitionRejected
            from ..approvals.rbac import AccessDenied
            for gate_id in ("G1","G2"):
                try:self.transitions.require_fresh_passing_gate(run.run_id,gate_id,now=moment)
                except (TransitionRejected,AccessDenied):blockers.append("UPSTREAM_"+gate_id+"_INVALID")
            try:
                deployment = self.store.get_deployment(request.deployment_id)
            except KeyError:
                blockers.append("DEPLOYMENT_MISSING")
            else:
                if (deployment.run_id != run.run_id or deployment.status is not DeploymentStatus.SUCCEEDED
                        or deployment.authorization_id != request.authorization_id
                        or deployment.release_artifact_digest != request.artifact_digest
                        or deployment.environment_id != request.target_environment):
                    blockers.append("DEPLOYMENT_BINDING_INVALID")
                try:
                    authorization = self.store.get_authorization(deployment.authorization_id)
                    release = self.store.get_release(deployment.release_id)
                except KeyError:
                    blockers.append("RELEASE_OR_AUTHORIZATION_MISSING")
                else:
                    if (authorization.release_id != release.release_id
                            or release.run_id != run.run_id
                            or authorization.project_id != run.project_id
                            or authorization.artifact_digest != deployment.release_artifact_digest
                            or authorization.commit_sha != release.commit_sha
                            or set(deployment.target_ids) != set(authorization.target_ids)):
                        blockers.append("RELEASE_OR_AUTHORIZATION_BINDING_INVALID")
            for field in ("smoke_check_passed", "health_check_passed", "rollback_ready"):
                if getattr(request, field) is not True:
                    blockers.append(field.upper())
            if request.deployment_id:
                try:
                    deployment = self.store.get_deployment(request.deployment_id)
                    if deployment.environment_id != "simulation":
                        blockers.extend(self._verify_deployment_evidence(request, deployment, moment))
                except (KeyError, TypeError, ValueError, PermissionError, OSError, AccessDenied):
                    blockers.append("DEPLOYMENT_EVIDENCE_INVALID")
        return blockers

    def _verify_deployment_evidence(self, request, deployment, moment):
        from ..contracts.enums import AuthorizationStatus, ToolExecutionStatus, TrustLevel
        from ..approvals import RBACService
        if self.archive is None or not request.evidence_artifact_id: return ["DEPLOYMENT_EVIDENCE_REQUIRED"]
        artifact = self.store.get_artifact(request.evidence_artifact_id)
        body = self.archive.read(artifact.artifact_id, run_id=request.run_id)
        receipt = self.store.find_tool_execution_by_key(body["effect_id"])
        authorization = self.store.get_authorization(deployment.authorization_id)
        rbac = RBACService(self.store)
        rbac.require_human(authorization.issued_by)
        if (artifact.type != "DEPLOYMENT_EVIDENCE" or artifact.producer_task_id != "deployment-observer"
                or artifact.trust_level is not TrustLevel.VERIFIED_INTERNAL or artifact.sha256 != request.input_digest
                or body["deployment_id"] != deployment.deployment_id or not receipt
                or receipt.status is not ToolExecutionStatus.SUCCEEDED
                or receipt.external_operation_id != deployment.external_operation_id
                or body["artifact_digest"] != deployment.release_artifact_digest
                or body["health"].get("healthy") is not request.health_check_passed
                or body["health"].get("artifact_digest") != deployment.release_artifact_digest
                or request.smoke_check_passed is not body["health"].get("healthy")
                or authorization.expires_at <= moment or authorization.issued_at > moment
                or authorization.status is AuthorizationStatus.REVOKED
                or "release_approver" not in rbac.roles_of(authorization.issued_by, authorization.project_id, moment)):
            return ["DEPLOYMENT_PROOF_OR_AUTHORIZATION_INVALID"]
        return []

    def _verify_delivery_evidence(self, request, run):
        if self.archive is None:
            return ["EVIDENCE_RESOLVER_MISSING"]
        artifact = self.store.get_artifact(request.evidence_artifact_id)
        body = self.archive.read(artifact.artifact_id, run_id=run.run_id)
        if artifact.type != "DELIVERY_EVIDENCE" or artifact.sha256 != request.input_digest:
            return ["EVIDENCE_DIGEST_INVALID"]
        blockers = []
        if any(body.get(key) != run.baseline_versions.get(key) for key in ("spec", "architecture", "commit")):
            blockers.append("EVIDENCE_BASELINE_MISMATCH")
        test_artifact = self.store.get_artifact(body["test_id"])
        test = self.archive.read(body["test_id"], run_id=run.run_id)
        if (test_artifact.type != "TEST_EXECUTION" or test_artifact.producer_task_id != "test-executor"
                or test.get("decision") != "PASS" or test.get("commit_sha") != body["commit"]
                or test.get("spec_digest") != body["spec"] or test.get("architecture_digest") != body["architecture"]
                or test.get("required_tests_complete") is not True or test.get("integrity_valid") is not True):
            blockers.append("TEST_EVIDENCE_INVALID")
        for field in ("acceptance_id", "review_id"):
            if field == "review_id" and not body["review_triggered"]:
                continue
            reply = self.archive.read(body[field], run_id=run.run_id)
            expected_role = "engineering-leader" if field == "acceptance_id" else "code-review"
            if reply.get("role") != expected_role:
                blockers.append(field.upper() + "_ROLE_INVALID")
            verdict = reply["output"]
            if verdict.get("accepted") is not True or verdict.get("input_digest") != body["commit"]:
                blockers.append(field.upper() + "_INVALID")
        security = self.archive.read(body["security_id"], run_id=run.run_id)["output"]
        if security["input_digest"] != body["commit"] or any(
            item["severity"] in {"CRITICAL", "HIGH"} for item in security["findings"]
        ):
            blockers.append("SECURITY_EVIDENCE_INVALID")
        scan_artifact = self.store.get_artifact(body["scan_id"])
        scan = self.archive.read(body["scan_id"], run_id=run.run_id)
        if scan_artifact.type != "SECURITY_SCAN" or scan.get("commit") != body["commit"] or any(
            item["severity"] in {"CRITICAL", "HIGH"} for item in scan["findings"]
        ):
            blockers.append("LOCAL_SCAN_INVALID_OR_BLOCKING")
        return blockers

    @atomic
    def invalidate_dependents(self, run_id, reason, *, up_to_gate=None):
        order = [GateId.G1, GateId.G2, GateId.G3]
        limit = order.index(up_to_gate) if up_to_gate else len(order)
        changed = []
        for gate in self.store.gate_results_for(run_id):
            if gate.gate_id in order[:limit] and gate.status in {GateStatus.PENDING, GateStatus.PASSED}:
                changed.append(self.transitions.transition_gate(gate, GateStatus.STALE))
        return changed
