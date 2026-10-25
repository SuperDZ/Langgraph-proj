"""Phase 1 父图与三部门子图。所有阶段、门禁和副作用由程序控制。"""

from pathlib import Path
import sqlite3
from typing import TypedDict

from langgraph.checkpoint.sqlite import SqliteSaver
from langgraph.graph import START, END, StateGraph
from langgraph.types import Command, interrupt
from langgraph.errors import GraphRecursionError

from ..approvals import ApprovalRequestService, compute_input_digest
from ..approvals.releases import ReleaseService
from ..contracts.delivery import ArchitectureDesign, EngineeringPlan, PatchProposal, ProductSpec, SecurityReport, TestDiagnosis, Verdict
from ..contracts.enums import ActorType, EventType, GateId, GateStatus, HARD_BLOCKING_SEVERITIES, IssueCategory, IssueStatus, RunPhase, RunStatus, RunType, Severity, TrustLevel
from ..contracts.models import GateEvaluationRequest, Issue
from ..orchestration import GateEvaluator, StateTransitionService, TransitionRejected
from ..routing import LoopRouter
from ..runtime.security import SecurityIssueService, scan_sources
from ...knowledge.archive import canonical


class DeliveryState(TypedDict, total=False):
    run_id: str
    task: str
    spec_id: str
    spec_digest: str
    architecture_id: str
    architecture_digest: str
    product_round: int
    architecture_round: int
    attempt: int
    local_attempt: int
    security_rework_round: int
    remediation_id: str
    g2_passed: bool
    front_accepted: bool
    ux_accepted: bool
    engineering_accepted: bool
    review_accepted: bool
    test_passed: bool
    commit_sha: str
    review_id: str
    test_id: str
    plan_id: str
    acceptance_id: str
    security_id: str
    scan_id: str
    release_id: str
    deployment_id: str
    previous_failure: str


class WorkflowBlocked(RuntimeError):
    pass


class DeliveryWorkflow:
    def __init__(self, *, store, archive, workspace, workers, runner, config, rbac, checkpoint_path, engineering_coordinator=None):
        self.store, self.archive, self.workspace, self.workers = store, archive, workspace, workers
        self.runner, self.config, self.rbac = runner, config, rbac
        self.engineering_coordinator = engineering_coordinator
        self.execution_mode = "phase3" if engineering_coordinator is not None else "phase2" if workers.managed else "phase1"
        required_roles = {"product-analyst", "product-leader", "ux-agent", "product-expert", "architecture-expert",
                          "expert-leader", "engineering-leader", "backend", "testing", "code-review", "security-expert"}
        if not required_roles.issubset(config.role_profiles) or not set(config.role_profiles.values()).issubset(workers.adapters):
            raise ValueError("角色 Profile 或适配器缺失，禁止启动")
        self.transitions = StateTransitionService(store, allow_simulated_deployment=True)
        self.approvals = ApprovalRequestService(store, rbac)
        self.gates = GateEvaluator(store, self.transitions, self.approvals, archive=archive)
        self.releases = ReleaseService(store, self.transitions, rbac)
        self.router = LoopRouter(store)
        self.security_issues = SecurityIssueService(store, archive, workspace, self.router)
        self.connection = sqlite3.connect(str(checkpoint_path), check_same_thread=False)
        self.saver = SqliteSaver(self.connection)
        self.product_graph = self._product_graph()
        self.front_graph = self._front_graph()
        self.engineering_graph = self._engineering_graph()
        self.security_graph = self._security_graph()
        graph = StateGraph(DeliveryState)
        graph.add_node("product", self.product_graph)
        graph.add_node("front_expert", self.front_graph)
        graph.add_node("g1", self._g1)
        graph.add_node("engineering", self.engineering_graph)
        graph.add_node("security_expert", self.security_graph)
        graph.add_node("g2", self._g2)
        graph.add_node("security_remediation", self._security_remediation)
        graph.add_node("release_authorization", self._release_wait)
        graph.add_node("simulate_deployment", self._simulate)
        graph.add_edge(START, "product")
        graph.add_edge("product", "front_expert")
        graph.add_conditional_edges("front_expert", lambda s: "g1" if s["front_accepted"] else "product")
        graph.add_edge("g1", "engineering")
        graph.add_edge("engineering", "security_expert")
        graph.add_edge("security_expert", "g2")
        graph.add_conditional_edges("g2", lambda s: "release_authorization" if s["g2_passed"] else "security_remediation")
        graph.add_edge("security_remediation", "engineering")
        graph.add_edge("release_authorization", "simulate_deployment")
        graph.add_edge("simulate_deployment", END)
        self.graph = graph.compile(checkpointer=self.saver)

    def _move(self, run_id, phase):
        run = self.store.get_run(run_id)
        if run.phase is not phase:
            self.transitions.transition(run_id, target_phase=phase, target_status=RunStatus.RUNNING,
                                        expected_version=run.state_version)

    def _bind(self, run_id, key, value):
        run = self.store.get_run(run_id)
        if run.baseline_versions.get(key) != value:
            self.transitions.bind_baseline(run_id, key=key, digest=value, expected_version=run.state_version)

    def _event(self, state, kind, actor, key, value):
        self.store.append_event(run_id=state["run_id"], event_type=kind, actor_id=actor,
            actor_type=ActorType.SYSTEM, payload_ref=canonical(value),
            idempotency_key=f"{state['run_id']}:{kind.value}:{key}")

    def _call(self, state, role, schema, context):
        return self.workers.call(run_id=state["run_id"], role=role, schema=schema, context=context)

    def _body(self, state, artifact_id):
        return self.archive.read(artifact_id, run_id=state["run_id"])

    def _verdict(self, state, role, digest, context):
        verdict, artifact = self._call(state, role, Verdict, {**context, "input_digest": digest})
        if verdict.input_digest != digest:
            raise WorkflowBlocked(f"{role} 的验收结论未绑定当前版本")
        return verdict, artifact

    def _product_graph(self):
        graph = StateGraph(DeliveryState)

        def analyst(state):
            round_no = state.get("product_round", 0) + 1
            if round_no > self.config.max_department_attempts:
                raise WorkflowBlocked("产品返工达到上限")
            self._move(state["run_id"], RunPhase.PRODUCT)
            spec, _ = self._call(state, "product-analyst", ProductSpec,
                {"task": state["task"], "attempt": round_no, "feedback": state.get("previous_failure", "")})
            if len({item.criterion_id for item in spec.criteria}) != len(spec.criteria):
                raise WorkflowBlocked("验收条件编号重复")
            artifact = self.archive.put(run_id=state["run_id"], kind="SPEC", producer="product-analyst",
                                         value=spec.model_dump(mode="json"))
            return {"spec_id": artifact.artifact_id, "spec_digest": artifact.sha256, "product_round": round_no}

        def ux(state):
            self._event(state, EventType.CHECK_TRIGGERED, "orchestrator", f"ux:{state['spec_digest']}",
                {"role": "ux-agent", "triggered": self.config.changes_ui, "reason": "trusted UI change flag"})
            if self.config.changes_ui:
                verdict, _ = self._verdict(state, "ux-agent", state["spec_digest"],
                    {"spec": self._body(state, state["spec_id"]), "attempt": state["product_round"],
                     "previous_failure": state.get("previous_failure", "")})
                if not verdict.accepted:
                    return {"ux_accepted": False, "previous_failure": "; ".join(verdict.reasons)}
            return {"ux_accepted": True}

        def accept(state):
            verdict, _ = self._verdict(state, "product-leader", state["spec_digest"],
                {"spec": self._body(state, state["spec_id"]), "attempt": state["product_round"]})
            if verdict.accepted:
                self._bind(state["run_id"], "spec", state["spec_digest"])
                self._event(state, EventType.DEPARTMENT_ACCEPTED, "product-leader", state["spec_digest"], {"department": "product"})
                self._move(state["run_id"], RunPhase.PRODUCT_AUDIT)
            return {"front_accepted": verdict.accepted, "previous_failure": "; ".join(verdict.reasons)}

        graph.add_node("analyst", analyst)
        graph.add_node("ux_trigger", ux)
        graph.add_node("product_acceptance", accept)
        graph.add_edge(START, "analyst")
        graph.add_edge("analyst", "ux_trigger")
        graph.add_conditional_edges("ux_trigger", lambda s: "product_acceptance" if s["ux_accepted"] else "analyst")
        graph.add_conditional_edges("product_acceptance", lambda s: END if s["front_accepted"] else "analyst")
        return graph.compile()

    def _front_graph(self):
        graph = StateGraph(DeliveryState)

        def audit(state):
            verdict, artifact = self._verdict(state, "product-expert", state["spec_digest"],
                {"spec": self._body(state, state["spec_id"]), "attempt": state["product_round"]})
            if not verdict.accepted:
                self._issue(state, IssueCategory.SPEC_DEFECT, Severity.MEDIUM, artifact.artifact_id, "; ".join(verdict.reasons))
                self._move(state["run_id"], RunPhase.PRODUCT)
            else:
                self._move(state["run_id"], RunPhase.ARCHITECTURE)
            return {"front_accepted": verdict.accepted, "previous_failure": "; ".join(verdict.reasons)}

        def architecture(state):
            round_no = state.get("architecture_round", 0) + 1
            if round_no > self.config.max_department_attempts:
                raise WorkflowBlocked("架构返工达到上限")
            design, _ = self._call(state, "architecture-expert", ArchitectureDesign,
                {"spec_digest": state["spec_digest"], "spec": self._body(state, state["spec_id"]),
                 "editable_paths": sorted(self.workspace.editable_paths), "attempt": round_no})
            if design.spec_digest != state["spec_digest"] or not set(design.editable_paths).issubset(self.workspace.editable_paths):
                raise WorkflowBlocked("架构版本不匹配或扩大修改范围")
            artifact = self.archive.put(run_id=state["run_id"], kind="ARCHITECTURE", producer="architecture-expert",
                                         value=design.model_dump(mode="json"))
            return {"architecture_id": artifact.artifact_id, "architecture_digest": artifact.sha256, "architecture_round": round_no}

        def accept(state):
            verdict, _ = self._verdict(state, "expert-leader", state["architecture_digest"],
                {"architecture": self._body(state, state["architecture_id"]), "attempt": state["architecture_round"]})
            if verdict.accepted:
                self._bind(state["run_id"], "architecture", state["architecture_digest"])
                self._event(state, EventType.DEPARTMENT_ACCEPTED, "expert-leader", state["architecture_digest"], {"mode": "FRONT"})
                self._move(state["run_id"], RunPhase.G1)
            return {"front_accepted": verdict.accepted}

        graph.add_node("product_audit", audit)
        graph.add_node("architecture", architecture)
        graph.add_node("expert_acceptance", accept)
        graph.add_edge(START, "product_audit")
        graph.add_conditional_edges("product_audit", lambda s: "architecture" if s["front_accepted"] else END)
        graph.add_edge("architecture", "expert_acceptance")
        graph.add_conditional_edges("expert_acceptance", lambda s: END if s["front_accepted"] else "architecture")
        return graph.compile()

    def _g1(self, state):
        if self.store.get_run(state["run_id"]).phase is RunPhase.ENGINEERING:
            self.transitions.require_fresh_passing_gate(state["run_id"], "G1")
            return {}
        request = GateEvaluationRequest(run_id=state["run_id"], gate_id=GateId.G1, policy_version=self.gates.policy_version,
            input_digest=compute_input_digest(state["spec_digest"], state["architecture_digest"]),
            spec_digest=state["spec_digest"], architecture_digest=state["architecture_digest"],
            product_leader_accepted=True, product_audit_passed=True, architecture_review_passed=True,
            user_requested_extra_confirmation=self.config.require_confirmation)
        result = self.gates.evaluate(request)
        if result.status is GateStatus.PENDING:
            interrupt({"kind": "G1_CONFIRMATION", "approval_ids": result.approval_ids})
            result = self.gates.evaluate(request)
        if result.status is not GateStatus.PASSED:
            raise WorkflowBlocked("G1 尚未取得有效批准")
        self._move(state["run_id"], RunPhase.ENGINEERING)
        return {}

    def _engineering_graph(self):
        graph = StateGraph(DeliveryState)

        def plan(state):
            self.transitions.require_fresh_passing_gate(state["run_id"], "G1")
            result, artifact = self._call(state, "engineering-leader", EngineeringPlan,
                {"spec": self._body(state, state["spec_id"]), "architecture": self._body(state, state["architecture_id"]),
                 "remediation": self._body(state, state["remediation_id"]) if state.get("remediation_id") else None, "mode": "ENTRY"})
            expected = {item["criterion_id"] for item in self._body(state, state["spec_id"])["criteria"]}
            if set(result.test_criteria_ids) != expected:
                raise WorkflowBlocked("研发计划未覆盖全部验收条件")
            return {"plan_id": artifact.artifact_id, "local_attempt": 0}

        def backend(state):
            attempt = state.get("attempt", 0) + 1
            local_attempt = state.get("local_attempt", state.get("attempt", 0)) + 1
            if local_attempt > self.config.max_rework_rounds:
                raise WorkflowBlocked("研发局部返工达到上限")
            architecture = self._body(state, state["architecture_id"])
            allowed_paths = set(architecture["editable_paths"])
            if self.engineering_coordinator is not None:
                commit = self.engineering_coordinator.develop({**state,"attempt":attempt}, architecture,
                    self._body(state,state["plan_id"])["output"])
                self._bind(state["run_id"],"commit",commit)
                return {"attempt":attempt,"local_attempt":local_attempt,"commit_sha":commit}
            receipt = next((a for a in self.store.artifacts_for(state["run_id"])
                            if a.type == "BACKEND_CANDIDATE" and a.producer_task_id == f"backend:{attempt}"), None)
            if receipt:
                proposal = PatchProposal.model_validate(self._body(state, receipt.artifact_id))
            else:
                sources = {path: (self.workspace.root / path).read_text(encoding="utf-8") for path in sorted(allowed_paths)}
                from ..runtime.workspace import file_digest
                hashes = {path: file_digest(self.workspace.root / path) for path in sorted(allowed_paths)}
                proposal, _ = self._call(state, "backend", PatchProposal,
                    {"attempt": attempt, "sources": sources, "hashes": hashes,
                     "plan": self._body(state, state["plan_id"])["output"], "architecture": architecture,
                     "remediation": self._body(state, state["remediation_id"]) if state.get("remediation_id") else None,
                     "spec": self._body(state, state["spec_id"]), "feedback": state.get("previous_failure", "")})
                self.archive.put(run_id=state["run_id"], kind="BACKEND_CANDIDATE", producer=f"backend:{attempt}",
                                 value=proposal.model_dump(mode="json"))
            if any(change.path not in allowed_paths for change in proposal.changes):
                raise WorkflowBlocked("补丁超出已批准的架构修改范围")
            commit = self.workspace.apply(proposal, attempt=attempt)
            self._bind(state["run_id"], "commit", commit)
            return {"attempt": attempt, "local_attempt": local_attempt, "commit_sha": commit}

        def review(state):
            self.workspace.assert_revision(state["commit_sha"])
            baseline = self.workspace.git("rev-list", "--max-parents=0", "HEAD").splitlines()[0]
            paths = self.workspace.git("diff", "--name-only", baseline, state["commit_sha"]).splitlines()
            triggered = self.config.production_code_changed or any(path.startswith("src/main/") for path in paths)
            self._event(state, EventType.CHECK_TRIGGERED, "orchestrator", f"review:{state['commit_sha']}",
                {"role": "code-review", "triggered": triggered, "commit": state["commit_sha"]})
            if not triggered:
                return {"review_accepted": True, "review_id": ""}
            verdict, artifact = self._verdict(state, "code-review", state["commit_sha"],
                {"diff": self.workspace.git("diff", baseline, state["commit_sha"]), "attempt": state["attempt"]})
            if not verdict.accepted:
                self._rework(state, "CODE_REVIEW_REJECTED")
            return {"review_accepted": verdict.accepted, "review_id": artifact.artifact_id,
                    "previous_failure": "; ".join(verdict.reasons)}

        def test(state):
            self.workspace.assert_revision(state["commit_sha"])
            report = None
            for previous in self.store.artifacts_for(state["run_id"]):
                if previous.type == "TEST_EXECUTION":
                    body = self._body(state, previous.artifact_id)
                    if (body.get("commit_sha") == state["commit_sha"] and body.get("attempt") == state["attempt"]
                            and body.get("spec_digest") == state["spec_digest"]
                            and body.get("architecture_digest") == state["architecture_digest"]):
                        report = body
                        break
            if report is None:
                report = self.runner.run(self.workspace, attempt=state["attempt"])
            if report.get("commit_sha") != state["commit_sha"]:
                raise WorkflowBlocked("测试未绑定当前 Commit")
            artifact = self.archive.put(run_id=state["run_id"], kind="TEST_EXECUTION", producer="test-executor",
                value={**report, "attempt": state["attempt"], "spec_digest": state["spec_digest"], "architecture_digest": state["architecture_digest"]},
                trust=TrustLevel.VERIFIED_INTERNAL)
            self._event(state, EventType.TEST_EXECUTED, "testing", f"{state['attempt']}:{artifact.artifact_id}",
                {"artifact_id": artifact.artifact_id, "decision": report["decision"], "commit": state["commit_sha"]})
            if report["decision"] == "INCONCLUSIVE":
                raise WorkflowBlocked("测试证据不完整，不能视作 PASS")
            if report["decision"] != "PASS":
                diagnosis, _ = self._call(state, "testing", TestDiagnosis,
                    {"report": {k: report[k] for k in ("decision", "commit_sha", "total", "failed", "skipped",
                                                       "required_tests_complete", "integrity_valid", "exit_code", "tests", "integration_checks") if k in report},
                     "log_tail": report.get("log", "")[-8000:]})
                if diagnosis.category != "CODE_DEFECT":
                    raise WorkflowBlocked("测试自身或未分类问题需审查，禁止自动削弱测试")
                self._rework(state, diagnosis.explanation)
            return {"test_id": artifact.artifact_id, "test_passed": report["decision"] == "PASS",
                    "previous_failure": canonical({"log":report.get("log", "")[-8000:],"integration_checks":report.get("integration_checks",[])}) if report["decision"] != "PASS" else ""}

        def accept(state):
            verdict, artifact = self._verdict(state, "engineering-leader", state["commit_sha"],
                {"mode": "EXIT", "test": self._body(state, state["test_id"]), "review_id": state["review_id"]})
            if not verdict.accepted:
                self._rework(state, "; ".join(verdict.reasons))
                return {"engineering_accepted": False, "previous_failure": "; ".join(verdict.reasons)}
            self._event(state, EventType.DEPARTMENT_ACCEPTED, "engineering-leader", state["commit_sha"], {"department": "engineering"})
            self._move(state["run_id"], RunPhase.SECURITY_REVIEW)
            return {"acceptance_id": artifact.artifact_id, "engineering_accepted": True}

        for name, node in {"plan": plan, "backend": backend, "review": review, "testing": test, "engineering_acceptance": accept}.items():
            graph.add_node(name, node)
        graph.add_edge(START, "plan")
        graph.add_edge("plan", "backend")
        graph.add_edge("backend", "review")
        graph.add_conditional_edges("review", lambda s: "testing" if s["review_accepted"] else "backend")
        graph.add_conditional_edges("testing", lambda s: "engineering_acceptance" if s["test_passed"] else "backend")
        graph.add_conditional_edges("engineering_acceptance", lambda s: END if s["engineering_accepted"] else "backend")
        return graph.compile()

    def _rework(self, state, reason):
        self._event(state, EventType.LOCAL_REWORK, "orchestrator", f"{state['attempt']}:{reason[:80]}",
            {"attempt": state["attempt"], "reason": reason, "target": "engineering-workers" if self.engineering_coordinator else "backend"})
        if state.get("local_attempt", state["attempt"]) >= self.config.max_rework_rounds:
            raise WorkflowBlocked("同一缺陷连续无效返工达到上限")

    def _issue(self, state, category, severity, evidence_id, description):
        from hashlib import sha256
        key = sha256(f"{severity.value}:{description}".encode()).hexdigest()
        issue = Issue(issue_id=f"{state['run_id']}:{category.value}:{evidence_id}:{key}", run_id=state["run_id"],
            category=category, severity=severity, description=description or category.value, evidence_artifact_ids=[evidence_id])
        if not any(i.issue_id == issue.issue_id for i in self.store.list_issues(state["run_id"])):
            self.router.route(issue, source_event_id=evidence_id)

    def _security_graph(self):
        graph = StateGraph(DeliveryState)

        def scan(state):
            body = scan_sources(self.workspace, self.store.get_run(state["run_id"]).baseline_versions)
            evidence = self.archive.put(run_id=state["run_id"], kind="SECURITY_SCAN", producer="local-policy-scanner",
                value=body,
                trust=TrustLevel.VERIFIED_INTERNAL)
            self.security_issues.record_scan(state["run_id"], evidence.artifact_id, test_id=state["test_id"],
                review_id=state["review_id"], acceptance_id=state["acceptance_id"])
            report, artifact = self._call(state, "security-expert", SecurityReport,
                {"input_digest": state["commit_sha"], "scan": self._body(state, evidence.artifact_id)})
            if report.input_digest != state["commit_sha"]:
                raise WorkflowBlocked("安全报告未绑定当前 Commit")
            for finding in report.findings:
                # 专家候选没有经过确定性根因验证，不允许固定指派研发。
                self._issue(state, IssueCategory.SECURITY_FINDING, Severity(finding.severity), artifact.artifact_id, finding.description)
            return {"security_id": artifact.artifact_id, "scan_id": evidence.artifact_id}

        graph.add_node("security_expert", scan)
        graph.add_edge(START, "security_expert")
        graph.add_edge("security_expert", END)
        return graph.compile()

    def _g2(self, state):
        self.workspace.assert_revision(state["commit_sha"])
        if self.store.get_run(state["run_id"]).phase is RunPhase.RELEASE_AUTHORIZATION:
            self.transitions.require_fresh_passing_gate(state["run_id"], "G2")
            return {"g2_passed": True}
        self._move(state["run_id"], RunPhase.G2)
        artifact = self.archive.put(run_id=state["run_id"], kind="DELIVERY_EVIDENCE", producer="orchestrator:g2",
            value={"spec": state["spec_digest"], "architecture": state["architecture_digest"], "commit": state["commit_sha"],
                   "test_id": state["test_id"], "review_id": state["review_id"], "review_triggered": bool(state["review_id"]),
                   "acceptance_id": state["acceptance_id"], "security_id": state["security_id"], "scan_id": state["scan_id"]},
            trust=TrustLevel.VERIFIED_INTERNAL)
        result = self.store.latest_gate_result(state["run_id"], "G2")
        if not (result and result.status is GateStatus.REJECTED and result.input_digest == artifact.sha256
                and self.store.get_run(state["run_id"]).status is RunStatus.BLOCKED):
            result = self.gates.evaluate(GateEvaluationRequest(run_id=state["run_id"], gate_id=GateId.G2,
                policy_version=self.gates.policy_version, input_digest=artifact.sha256, evidence_artifact_id=artifact.artifact_id,
                engineering_leader_accepted=True, required_tests_complete=True))
        if result.status is not GateStatus.PASSED:
            return {"g2_passed": False}
        self._move(state["run_id"], RunPhase.RELEASE_AUTHORIZATION)
        return {"g2_passed": True}

    def _security_remediation(self, state):
        self.workspace.assert_revision(state["commit_sha"])
        with self.store.transaction():
            gate = self.store.latest_gate_result(state["run_id"], "G2")
            if gate is None or gate.status is not GateStatus.REJECTED:
                raise WorkflowBlocked("整改必须引用被拒绝的 G2")
            producer = f"orchestrator:remediation:{gate.gate_result_id}"
            previous = next((a for a in self.store.artifacts_for(state["run_id"])
                             if a.type == "REMEDIATION_ORDER" and a.producer_task_id == producer), None)
            if previous:
                order = self._body(state, previous.artifact_id)
                return {"remediation_id": previous.artifact_id, "security_rework_round": order["round"],
                        "local_attempt": 0, "previous_failure": canonical(order)}
            round_no = state.get("security_rework_round", 0) + 1
            if round_no > self.config.max_department_attempts:
                raise WorkflowBlocked("安全整改达到部门返工上限")
            if state.get("remediation_id") and self._body(state, state["remediation_id"])["commit"] == state["commit_sha"]:
                raise WorkflowBlocked("安全整改未产生新 Commit，停止无效返工")
            issues = self.store.open_issues_by_severity(state["run_id"], HARD_BLOCKING_SEVERITIES)
            if not issues or not all(self.security_issues.repairable(issue) for issue in issues):
                raise WorkflowBlocked("G2 存在未验证根因或非代码阻断项，等待人工分派")
            # 仅验证过的确定性扫描项允许自动整改；其他 Gate 阻断不能被夹带跳过。
            allowed = {"LOCAL_SCAN_INVALID_OR_BLOCKING", *[f"UNRESOLVED:{i.issue_id}" for i in issues]}
            if not set(gate.blocker_issue_ids).issubset(allowed):
                raise WorkflowBlocked("G2 还有其他证据阻断，不能自动整改")
            self.transitions.require_fresh_passing_gate(state["run_id"], "G1")
            run = self.store.get_run(state["run_id"])
            order = {"round": round_no, "gate_id": gate.gate_result_id, "target_leader": "engineering-leader",
                     "spec": state["spec_digest"], "architecture": state["architecture_digest"], "commit": state["commit_sha"],
                     "issues": [issue.model_dump(mode="json") for issue in issues],
                     "impact": "code-only; retain G1; repeat development, code review, tests, acceptance and security review"}
            artifact = self.archive.put(run_id=state["run_id"], kind="REMEDIATION_ORDER", producer=producer,
                                        value=order, trust=TrustLevel.VERIFIED_INTERNAL)
            self.transitions.transition(run.run_id, target_phase=RunPhase.ENGINEERING, target_status=RunStatus.RUNNING,
                                        expected_version=run.state_version, reason="verified security remediation to Engineering Leader")
            self._event(state, EventType.EXTERNAL_REWORK, "orchestrator", gate.gate_result_id, {"order_id": artifact.artifact_id})
            return {"remediation_id": artifact.artifact_id, "security_rework_round": round_no,
                    "local_attempt": 0, "previous_failure": canonical(order)}

    def _release_wait(self, state):
        self.workspace.assert_revision(state["commit_sha"])
        release = self.releases.create(run_id=state["run_id"], commit_sha=state["commit_sha"], artifact_digest=state["commit_sha"])
        run = self.store.get_run(state["run_id"])
        if run.status is not RunStatus.WAITING_APPROVAL:
            self.transitions.transition(run.run_id, target_status=RunStatus.WAITING_APPROVAL, expected_version=run.state_version)
        authorization_id = interrupt({"kind": "SIMULATION_AUTHORIZATION", "release_id": release.release_id})
        from ..runtime.simulation import SimulatedDeployment
        SimulatedDeployment(self.store, self.transitions, self.rbac).validate_authorization(state["run_id"], authorization_id)
        return {"release_id": release.release_id, "deployment_id": authorization_id}

    def _simulate(self, state):
        self.workspace.assert_revision(state["commit_sha"])
        if self.store.get_run(state["run_id"]).status is RunStatus.COMPLETED:
            return {"deployment_id": self.store.deployments_for(state["run_id"])[-1].deployment_id}
        from ..runtime.simulation import SimulatedDeployment
        deployment = SimulatedDeployment(self.store, self.transitions, self.rbac).execute(state["run_id"], state["deployment_id"])
        self._move(state["run_id"], RunPhase.G3)
        result = self.gates.evaluate(GateEvaluationRequest(run_id=state["run_id"], gate_id=GateId.G3,
            policy_version=self.gates.policy_version, input_digest=deployment.deployment_id,
            deployment_id=deployment.deployment_id, authorization_id=deployment.authorization_id,
            artifact_digest=deployment.release_artifact_digest, target_environment="simulation",
            smoke_check_passed=True, health_check_passed=True, rollback_ready=True))
        if result.status is not GateStatus.PASSED:
            raise WorkflowBlocked("模拟 G3 失败")
        self.transitions.advance_to_delivery(state["run_id"], expected_version=self.store.get_run(state["run_id"]).state_version)
        return {"deployment_id": deployment.deployment_id}

    def start(self, run_id, task):
        from hashlib import sha256
        digest = sha256(canonical(self.config.model_dump(mode="json")).encode()).hexdigest()
        existing = self.store.find_run(run_id)
        saved_mode=self.store.runtime_get("workflow_mode",run_id)
        if existing is not None and not saved_mode:
            from ..runtime.workers import mode_from_profiles
            saved_mode={"mode":mode_from_profiles(self.config.role_profiles)}
        if saved_mode and saved_mode["mode"]!=self.execution_mode:
            raise ValueError("同一 Run 的运行模式不能切换")
        if existing is None:
            self.transitions.create_run(run_id=run_id, run_type=RunType.DELIVERY, project_id=self.config.project_id,
                trigger_source="USER", config_snapshot_id=digest)
            self.transitions.transition(run_id, target_status=RunStatus.RUNNING)
            self.archive.put(run_id=run_id, kind="CONFIG_SNAPSHOT", producer="orchestrator", value=self.config.model_dump(mode="json"),
                             trust=TrustLevel.VERIFIED_INTERNAL)
            self.store.runtime_put("workflow_mode",run_id,{"mode":self.execution_mode})
        elif existing.config_snapshot_id != digest:
            raise ValueError("运行中配置快照不可更换")
        elif not self.store.runtime_get("workflow_mode",run_id):
            self.store.runtime_put("workflow_mode",run_id,saved_mode)
        snapshot = self.graph.get_state(self._config(run_id))
        if snapshot.values:
            if snapshot.values["task"] != task:
                raise ValueError("同一 Run 不允许替换任务")
            if existing.status is RunStatus.RUNNING and snapshot.next:
                return self._invoke(run_id, None)
            return self.summary(run_id)
        return self._invoke(run_id, {"run_id": run_id, "task": task})

    def _config(self, run_id):
        return {"configurable": {"thread_id": run_id}, "recursion_limit": self.config.max_steps}

    def _assert_config(self, run_id):
        from hashlib import sha256
        digest = sha256(canonical(self.config.model_dump(mode="json")).encode()).hexdigest()
        if self.store.get_run(run_id).config_snapshot_id != digest:
            raise ValueError("恢复时配置快照不匹配")

    def _invoke(self, run_id, value):
        try:
            self.graph.invoke(value, self._config(run_id))
        except (WorkflowBlocked, ValueError, PermissionError, TransitionRejected, GraphRecursionError) as exc:
            run = self.store.get_run(run_id)
            if run.status in {RunStatus.CANCEL_REQUESTED,RunStatus.CANCELLING,RunStatus.CANCELLED,RunStatus.NEEDS_RECONCILIATION,RunStatus.FAILED,RunStatus.COMPLETED}:
                return self.summary(run_id)
            self.archive.put(run_id=run_id, kind="WORKFLOW_BLOCKED", producer="orchestrator", value={"reason": str(exc)})
            if run.status is not RunStatus.BLOCKED:
                self.transitions.transition(run_id, target_status=RunStatus.BLOCKED, expected_version=run.state_version)
        except Exception as exc:
            # 未预期异常（工作区文件缺失、checkpoint 锁、模型契约错误等）同样必须
            # 离开 RUNNING 并落证据，否则会形成重启后无限重放的僵尸 Run。
            run = self.store.get_run(run_id)
            if run.status in {RunStatus.CANCEL_REQUESTED,RunStatus.CANCELLING,RunStatus.CANCELLED,RunStatus.NEEDS_RECONCILIATION,RunStatus.FAILED,RunStatus.COMPLETED}:
                return self.summary(run_id)
            import traceback
            self.archive.put(run_id=run_id, kind="WORKFLOW_BLOCKED", producer="orchestrator",
                             value={"reason": f"unexpected {type(exc).__name__}: {exc}",
                                    "traceback": traceback.format_exc()[-8000:]})
            if run.status is not RunStatus.BLOCKED:
                self.transitions.transition(run_id, target_status=RunStatus.BLOCKED, expected_version=run.state_version)
        return self.summary(run_id)

    def confirm_g1(self, run_id, principal_id):
        from ..contracts.enums import ApprovalDecision
        self._assert_config(run_id)
        run = self.store.get_run(run_id)
        if run.phase is not RunPhase.G1 or run.status is not RunStatus.WAITING_APPROVAL:
            raise ValueError("当前 Run 不在 G1 人工确认等待点")
        for approval in self.store.approval_requests_for(run_id):
            if approval.decision is None:
                self.approvals.decide(approval_id=approval.approval_id, principal_id=principal_id, decision=ApprovalDecision.APPROVE)
        return self._invoke(run_id, Command(resume=True))

    def authorize_simulation(self, run_id, principal_id, decision=None):
        from ..contracts.enums import ApprovalDecision, ReleaseAction
        if decision is None:
            decision = ApprovalDecision.APPROVE
        self._assert_config(run_id)
        run = self.store.get_run(run_id)
        if run.status is RunStatus.COMPLETED:
            self.rbac.require_human(principal_id)
            self.rbac.assert_project_access(principal_id, run.project_id)
            return self.summary(run_id)
        if run.phase is not RunPhase.RELEASE_AUTHORIZATION or run.status is not RunStatus.WAITING_APPROVAL:
            raise ValueError("当前 Run 不在模拟发布授权等待点")
        self.workspace.assert_revision(run.baseline_versions["commit"])
        release = next((r for r in reversed(self.store.releases_for(run_id))), None)
        if release is None:
            raise ValueError("等待授权的 Release 不存在")
        request = self.releases.request(release_id=release.release_id, principal_id=principal_id,
            environment_id="simulation", target_ids=["local-simulator"], action_scope=[ReleaseAction.DEPLOY])
        authorization = self.releases.decide(request_id=request.authorization_request_id, principal_id=principal_id,
                                             decision=decision)
        if decision is not ApprovalDecision.APPROVE:
            # 拒绝：Run 已由 decide 迁移到 BLOCKED，不恢复图执行；
            # 重新授权可再次进入等待点。
            return self.summary(run_id)
        return self._invoke(run_id, Command(resume=authorization.authorization_id))

    def summary(self, run_id):
        run = self.store.get_run(run_id)
        snapshot = self.graph.get_state(self._config(run_id))
        return {"run_id": run_id, "phase": run.phase.value, "status": run.status.value,
                "state_version": run.state_version, "baseline": run.baseline_versions,
                "checkpoint_next": list(snapshot.next), "mode": ("MANAGED_MODELS_LOCAL_TESTS_SIMULATED_DEPLOYMENT" if self.workers.managed else "SCRIPTED_WORKERS_LOCAL_TESTS_SIMULATED_DEPLOYMENT"),
                "workspace": str(self.workspace.root), "event_count": len(self.store.events_for(run_id))}

    def close(self):
        if self.workers.managed and self.workers.managed.tools:
            self.workers.managed.tools.close()
        self.connection.close()
