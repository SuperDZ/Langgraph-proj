"""执行验收测试并保存 REQ→AC→测试→执行结果；不把测试映射当完整验收。"""

import argparse
import importlib.metadata
import json
from pathlib import Path
import platform
import re
import os

import pytest


class Recorder:
    def __init__(self):
        self.metadata = {}
        self.results = {}

    def pytest_collection_modifyitems(self, items):
        for item in items:
            self.metadata[item.nodeid] = {
                "acceptance": sorted({str(value) for mark in item.iter_markers("ac") for value in mark.args}),
                "requirements": sorted({str(value) for mark in item.iter_markers("requirements") for value in mark.args}),
            }

    def pytest_runtest_logreport(self, report):
        if report.when == "call" or report.failed or report.skipped:
            self.results[report.nodeid] = report.outcome.upper()


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=Path, default=Path("docs/phase0-validation.json"))
    parser.add_argument("--java", action="store_true", help="执行真实 Maven/Spring Boot 集成测试")
    parser.add_argument("--java-home")
    parser.add_argument("--maven")
    args = parser.parse_args()
    if args.java:
        os.environ["AGENTLOOP_RUN_JAVA"] = "1"
        if args.java_home:
            os.environ["AGENTLOOP_JAVA_HOME"] = str(Path(args.java_home).resolve())
        if args.maven:
            os.environ["AGENTLOOP_MAVEN"] = str(Path(args.maven).resolve())
    root = Path(__file__).resolve().parents[2]
    spec = (root / "notes/multi_agent_loop_platform_design_v1.2.md").read_text(encoding="utf-8")
    requirements = sorted(set(re.findall(r"^\| (REQ-\d+) \|", spec, re.M)))
    ac_rows = re.findall(r"^\| (AC-\d+) \| ([^|]+) \|", spec, re.M)
    ac_ids = [ac for ac, _ in ac_rows]
    if len(ac_ids) != len(set(ac_ids)) or set(ac_ids) != {f"AC-{n:02}" for n in range(1, 60)}:
        raise ValueError("AC 编号不连续或不唯一")
    links = {ac: re.findall(r"REQ-\d+", cell) for ac, cell in ac_rows}
    if set(requirements) != {f"REQ-{n:03}" for n in range(1, 50)}:
        raise ValueError("REQ 编号不连续或不唯一")
    if set(requirements) - {req for refs in links.values() for req in refs}:
        raise ValueError("存在未关联 AC 的需求")
    recorder = Recorder()
    exit_code = pytest.main([str(root / "src/agentloop/tests"), str(root / "src/week2/test"), "-q"], plugins=[recorder])
    tests = [{"nodeid": node, **meta, "result": recorder.results.get(node, "NOT_EXECUTED")}
             for node, meta in sorted(recorder.metadata.items())]
    unknown = {ac for test in tests for ac in test["acceptance"]} - set(ac_ids)
    unknown_req = {req for test in tests for req in test["requirements"]} - set(requirements)
    if unknown or unknown_req:
        raise ValueError(f"测试引用未知编号: {unknown | unknown_req}")
    from .core.contracts.models import utc_now
    report = {
        "generated_at": utc_now().isoformat(), "python": platform.python_version(),
        "platform": platform.platform(), "exit_code": int(exit_code),
        "scope": "Phase 0-3 core; real Git worktrees/merge recovery, authenticated local HTTP deployment, cancellation and G3 fault injection, maintenance children, MCP transports, week2 regression; Maven/Spring integration when enabled",
        "java_integration_requested": args.java,
        "versions": {name: importlib.metadata.version(name) for name in ["pydantic", "langgraph", "langgraph-checkpoint-sqlite", "pytest", "jsonschema", "PyYAML"]},
        "requirements_count": len(requirements), "acceptance_count": len(ac_ids),
        "traceability": [{"acceptance": ac, "requirements": links[ac],
            "status": "HAS_LINKED_TESTS_REVIEW_SCOPE" if any(ac in t["acceptance"] for t in tests) else "NO_EXECUTION_EVIDENCE",
            "tests": [t["nodeid"] for t in tests if ac in t["acceptance"]]} for ac in ac_ids],
        "tests": tests,
        "limitations": ["Linked passing tests do not imply the whole AC or all 49 REQs are accepted.",
            "Workers are scripted in acceptance tests; no live model quality or production deployment has been verified.",
            "Automatic G2 remediation covers deterministic Java process and frontend dynamic-code policies; unknown root causes require human classification.",
            "Live model credentials and account availability must pass preflight before online execution; offline tests do not prove live model quality.",
            "MCP stdio processes are human-approved local code, not an operating-system sandbox; Skill scripts are never executed.",
            "Live deployment evidence is limited to owned local static HTTP targets, not a customer production environment or a deployed Spring backend.",
            "Production is disabled by default; enabling it requires trusted target configuration, independent service identity, RBAC and exact human authorization.",
            "Full vulnerability scanning, OS-level sandboxing and external IdP integration are not established by these tests; Phase 4-5 remain incomplete."],
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    raise SystemExit(exit_code)


if __name__ == "__main__":
    main()
