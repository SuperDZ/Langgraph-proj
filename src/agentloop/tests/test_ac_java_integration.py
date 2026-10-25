"""真实 Spring Boot HTTP 断言与 Maven/JUnit 证据；需要显式启用 Java 集成测试。"""

import os

import pytest

from agentloop.core.contracts.enums import EventType
from agentloop.examples.demo import build_demo

pytestmark = [pytest.mark.java_integration,
    pytest.mark.skipif(os.environ.get("AGENTLOOP_RUN_JAVA") != "1", reason="需要显式启用真实 Java 集成环境"),
    pytest.mark.ac("AC-06"), pytest.mark.ac("AC-11"),
    pytest.mark.requirements("REQ-009", "REQ-011", "REQ-032")]


@pytest.mark.parametrize("security_example", [False, True])
def test_real_spring_http_bug_is_repaired_and_fixed_tests_remain_unchanged(tmp_path, security_example):
    workflow = build_demo(data_dir=tmp_path, run_id="spring-integration",
        java_home=os.environ.get("AGENTLOOP_JAVA_HOME"), maven=os.environ.get("AGENTLOOP_MAVEN"),
        security_example=security_example)
    protected = workflow.workspace.protected_digest()
    try:
        pending = workflow.start("spring-integration", "修复参数边界并保留原问候语")
        assert pending["status"] == "WAITING_APPROVAL", pending
        assert pending["phase"] == "RELEASE_AUTHORIZATION"
        reports = [workflow.archive.read(a.artifact_id, run_id="spring-integration")
                   for a in workflow.store.artifacts_for("spring-integration") if a.type == "TEST_EXECUTION"]
        assert [r["decision"] for r in reports] == (["FAIL", "PASS", "PASS"] if security_example else ["FAIL", "PASS"])
        assert reports[0]["failed"] == 2
        assert reports[1]["total"] == 4 and reports[1]["failed"] == 0
        assert reports[0]["commit_sha"] != reports[1]["commit_sha"]
        assert workflow.workspace.protected_digest() == protected
        assert workflow.store.count_events_of_type(EventType.LOCAL_REWORK) == 1
        if security_example:
            from agentloop.core.contracts.enums import GateStatus, IssueStatus
            assert [g.status for g in workflow.store.gate_results_for("spring-integration", "G2")] == [GateStatus.REJECTED, GateStatus.PASSED]
            assert workflow.store.list_issues("spring-integration")[0].status is IssueStatus.RESOLVED
            assert reports[1]["commit_sha"] != reports[2]["commit_sha"]
            assert reports[2]["total"] == 4 and reports[2]["failed"] == 0
            assert workflow.store.count_events_of_type(EventType.EXTERNAL_REWORK) == 1
        assert workflow.authorize_simulation("spring-integration", "demo-owner")["status"] == "COMPLETED"
    finally:
        workflow.close()
        workflow.store.close()
