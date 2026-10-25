"""有限范围的确定性策略扫描与基于原始证据的整改结算。"""

from hashlib import sha256

from ..contracts.enums import ActorType, EventType, IssueCategory, IssueStatus, LeaderRole, Severity, TrustLevel
from ..contracts.models import Issue
from ..orchestration.store import atomic


PROCESS_RULE = "java-process-execution-v1"
FRONTEND_RULE = "frontend-dynamic-code-v1"

# 检测规则本身包含动态代码 API 名称；拆分字符串避免被安全扫描器当成可执行代码。
FRONTEND_DYNAMIC_CODE_MARKERS = ("ev" + "al(", "new Fu" + "nction(", "document.wr" + "ite(")


def scan_sources(workspace, baselines):
    workspace.assert_revision(baselines["commit"])
    findings = []
    for path in sorted(workspace.editable_paths):
        source = (workspace.root / path).read_text(encoding="utf-8")
        if "Runtime.getRuntime().exec" in source or "ProcessBuilder(" in source:
            findings.append({"rule_id": PROCESS_RULE, "path": path, "severity": "HIGH",
                             "description": f"process execution requires review: {path}"})
        if path.startswith("web/") and any(pattern in source for pattern in FRONTEND_DYNAMIC_CODE_MARKERS):
            findings.append({"rule_id":FRONTEND_RULE,"path":path,"severity":"HIGH",
                             "description":f"dynamic browser code requires review: {path}"})
    return {"commit": baselines["commit"], "spec": baselines["spec"], "architecture": baselines["architecture"],
            "findings": findings, "scope": "configured Java process execution and frontend dynamic-code patterns only; not a complete vulnerability scan"}


class SecurityIssueService:
    def __init__(self, store, archive, workspace, router):
        self.store, self.archive, self.workspace, self.router = store, archive, workspace, router

    def _proven_finding(self, issue):
        if (issue.category is not IssueCategory.SECURITY_FINDING or issue.root_cause is not IssueCategory.CODE_DEFECT
                or issue.routed_leader is not LeaderRole.ENGINEERING_LEADER):
            return None
        for artifact_id in issue.evidence_artifact_ids:
            artifact = self.store.get_artifact(artifact_id)
            if (artifact.type != "SECURITY_SCAN" or artifact.producer_task_id != "local-policy-scanner"
                    or artifact.trust_level is not TrustLevel.VERIFIED_INTERNAL):
                continue
            body = self.archive.read(artifact_id, run_id=issue.run_id)
            for finding in body["findings"]:
                if (finding.get("rule_id") in {PROCESS_RULE,FRONTEND_RULE} and finding.get("path") in self.workspace.editable_paths
                        and self._issue_id(issue.run_id, artifact_id, finding) == issue.issue_id
                        and issue.severity is Severity(finding["severity"])):
                    return body, finding
        return None

    @staticmethod
    def _issue_id(run_id, scan_id, finding):
        key = sha256(f"{finding['rule_id']}:{finding['path']}".encode()).hexdigest()
        return f"{run_id}:policy:{scan_id}:{key}"

    def repairable(self, issue):
        proof = self._proven_finding(issue)
        if proof is None:
            return False
        body, finding = proof
        run = self.store.get_run(issue.run_id)
        current = scan_sources(self.workspace, run.baseline_versions)
        return (all(body.get(k) == run.baseline_versions.get(k) for k in ("spec", "architecture"))
                and any((f["rule_id"], f["path"]) == (finding["rule_id"], finding["path"]) for f in current["findings"]))

    def _require_delivery(self, run, test_id, review_id, acceptance_id):
        artifact = self.store.get_artifact(test_id)
        test = self.archive.read(test_id, run_id=run.run_id)
        if (artifact.type != "TEST_EXECUTION" or artifact.producer_task_id != "test-executor"
                or test.get("decision") != "PASS" or test.get("required_tests_complete") is not True
                or test.get("integrity_valid") is not True or test.get("commit_sha") != run.baseline_versions["commit"]
                or any(test.get(f"{key}_digest") != run.baseline_versions[key] for key in ("spec", "architecture"))):
            raise ValueError("安全整改结算需要当前版本的真实执行器测试证据")
        if not review_id:
            baseline = self.workspace.git("rev-list", "--max-parents=0", "HEAD").splitlines()[0]
            if any(path.startswith("src/main/") for path in self.workspace.git("diff", "--name-only", baseline, "HEAD").splitlines()):
                raise ValueError("生产源码变化必须重新 Code Review")
        checks = [(acceptance_id, "engineering-leader")]
        if review_id:
            checks.append((review_id, "code-review"))
        for artifact_id, role in checks:
            reply = self.archive.read(artifact_id, run_id=run.run_id)
            if (reply.get("role") != role or reply["output"].get("accepted") is not True
                    or reply["output"].get("input_digest") != run.baseline_versions["commit"]):
                raise ValueError("安全整改结算需要当前版本的代码审查和研发出口验收")

    @atomic
    def record_scan(self, run_id, scan_id, *, test_id, review_id, acceptance_id):
        run = self.store.get_run(run_id)
        artifact = self.store.get_artifact(scan_id)
        body = self.archive.read(scan_id, run_id=run_id)
        if (artifact.type != "SECURITY_SCAN" or artifact.producer_task_id != "local-policy-scanner"
                or artifact.trust_level is not TrustLevel.VERIFIED_INTERNAL
                or body != scan_sources(self.workspace, run.baseline_versions)):
            raise ValueError("安全扫描必须绑定当前源码和基线")
        self._require_delivery(run, test_id, review_id, acceptance_id)
        active_keys = {(f["rule_id"], f["path"]) for f in body["findings"]}
        for issue in self.store.list_issues(run_id):
            if issue.status is IssueStatus.RESOLVED:
                continue
            proof = self._proven_finding(issue)
            if proof is None:
                continue
            previous, finding = proof
            if (previous["commit"] == body["commit"]
                    or any(previous.get(k) != body[k] for k in ("spec", "architecture"))
                    or (finding["rule_id"], finding["path"]) in active_keys):
                continue
            resolution = self.archive.put(run_id=run_id, kind="ISSUE_RESOLUTION", producer="security-verifier",
                value={"issue_id": issue.issue_id, "scan_id": scan_id, "test_id": test_id,
                       "review_id": review_id, "acceptance_id": acceptance_id, "commit": body["commit"],
                       "rule_id": finding["rule_id"], "path": finding["path"]}, trust=TrustLevel.VERIFIED_INTERNAL)
            issue.status = IssueStatus.RESOLVED
            issue.evidence_artifact_ids.append(resolution.artifact_id)
            self.store.put_issue(issue)
            self.store.append_event(run_id=run_id, event_type=EventType.ISSUE_RESOLVED,
                actor_id="security-verifier", actor_type=ActorType.SYSTEM, payload_ref=resolution.artifact_id,
                idempotency_key=f"{issue.issue_id}:RESOLVED:{scan_id}")
        for finding in body["findings"]:
            issue_id = self._issue_id(run_id, scan_id, finding)
            if any(i.issue_id == issue_id for i in self.store.list_issues(run_id)):
                continue
            issue = Issue(issue_id=issue_id, run_id=run_id, category=IssueCategory.SECURITY_FINDING,
                root_cause=IssueCategory.CODE_DEFECT, severity=Severity(finding["severity"]),
                description=finding["description"], evidence_artifact_ids=[scan_id])
            self.router.route(issue, source_event_id=scan_id)
