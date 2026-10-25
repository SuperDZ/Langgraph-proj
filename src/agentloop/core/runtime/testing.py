"""实际子进程与 JUnit XML 决定测试结果，不接受 Agent 自报 PASS。"""

from pathlib import Path
import subprocess
import time
import xml.etree.ElementTree as ET


class SurefireRunner:
    def __init__(self, *, argv, environment, required_tests, timeout=180):
        self.argv, self.environment = tuple(argv), dict(environment)
        self.required_tests, self.timeout = frozenset(required_tests), timeout

    def run(self, workspace, *, attempt):
        commit, protected = workspace.commit(), workspace.protected_digest()
        reports = workspace.root / "target" / f"agentloop-reports-{attempt}"
        # 每次新尝试独立目录；恢复执行同次操作时，仅接受本次更新的 XML。
        start = time.time_ns()
        command = [*self.argv, f"-Dagentloop.reportsDirectory={reports}", "test"]
        try:
            result = subprocess.run(command, cwd=workspace.root, env=self.environment,
                capture_output=True, encoding="utf-8", errors="replace", timeout=self.timeout)
            exit_code, output = result.returncode, result.stdout + result.stderr
        except subprocess.TimeoutExpired as exc:
            return {"decision": "INCONCLUSIVE", "commit_sha": commit, "tests": [], "exit_code": None,
                    "total": 0, "failed": 0, "skipped": 0, "reason": "TIMEOUT", "log": str(exc)}
        names, total, failed, skipped = set(), 0, 0, 0
        try:
            for path in reports.glob("TEST-*.xml"):
                if path.stat().st_mtime_ns < start:
                    continue
                suite = ET.parse(path).getroot()
                for case in suite.iter("testcase"):
                    total += 1
                    names.add(case.attrib["name"])
                    failed += int(case.find("failure") is not None or case.find("error") is not None)
                    skipped += int(case.find("skipped") is not None)
        except (ET.ParseError, KeyError):
            return {"decision": "INCONCLUSIVE", "commit_sha": commit, "tests": [], "exit_code": exit_code,
                    "total": total, "failed": failed, "skipped": skipped, "reason": "INVALID_JUNIT", "log": output}
        integrity = (workspace.commit() == commit and workspace.protected_digest() == protected
                     and not workspace.git("status", "--porcelain", "--untracked-files=all"))
        complete = bool(names) and self.required_tests.issubset(names) and skipped == 0
        decision = "PASS" if complete and integrity and failed == 0 and exit_code == 0 else (
            "FAIL" if integrity and complete and failed > 0 else "INCONCLUSIVE")
        return {"decision": decision, "commit_sha": commit, "tests": sorted(names), "exit_code": exit_code,
                "total": total, "failed": failed, "skipped": skipped,
                "required_tests_complete": complete, "integrity_valid": integrity, "log": output,
                "command": command, "duration_seconds": round((time.time_ns() - start) / 1e9, 3)}
