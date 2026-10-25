"""受限写入、原文证据和真实测试执行器的失败闭合。"""

import os
from pathlib import Path
import sys

import pytest

from agentloop.core.contracts.delivery import FileChange, PatchProposal
from agentloop.core.contracts.enums import TrustLevel
from agentloop.core.orchestration import InMemoryStore
from agentloop.core.runtime.testing import SurefireRunner
from agentloop.core.runtime.workspace import GitWorkspace, file_digest
from agentloop.examples.demo import EDITABLE_PATH
from agentloop.knowledge.archive import ArtifactArchive

pytestmark = [pytest.mark.requirements("REQ-025", "REQ-032", "REQ-037")]


@pytest.fixture
def workspace(tmp_path):
    fixture = Path(__file__).resolve().parents[1] / "examples/spring-bug"
    return GitWorkspace.from_fixture(fixture, tmp_path / "workspace", editable_paths=[EDITABLE_PATH])


@pytest.mark.ac("AC-38")
@pytest.mark.parametrize("path", ["../outside", "/absolute", "C:/outside", "src\\main\\escape", "pom.xml",
                                   "src/test/java/example/HelloControllerTest.java"])
def test_backend_cannot_change_tests_build_config_or_escape_workspace(workspace, path):
    original = (workspace.root / EDITABLE_PATH).read_bytes()
    with pytest.raises(PermissionError):
        workspace.apply(PatchProposal(summary="illegal", changes=[FileChange(path=path, expected_sha256="x", content="evil")]), attempt=1)
    assert (workspace.root / EDITABLE_PATH).read_bytes() == original


@pytest.mark.ac("AC-38")
def test_all_changes_are_validated_before_first_write(workspace):
    original = (workspace.root / EDITABLE_PATH).read_bytes()
    proposal = PatchProposal(summary="mixed", changes=[
        FileChange(path=EDITABLE_PATH, expected_sha256=file_digest(workspace.root / EDITABLE_PATH), content="changed"),
        FileChange(path="pom.xml", expected_sha256="bad", content="disable tests"),
    ])
    with pytest.raises(PermissionError):
        workspace.apply(proposal, attempt=1)
    assert (workspace.root / EDITABLE_PATH).read_bytes() == original


@pytest.mark.ac("AC-44")
def test_stale_patch_is_rejected_without_commit_change(workspace):
    commit = workspace.commit()
    with pytest.raises(ValueError):
        workspace.apply(PatchProposal(summary="stale", changes=[FileChange(path=EDITABLE_PATH,
            expected_sha256="wrong", content="new content")]), attempt=1)
    assert workspace.commit() == commit


@pytest.mark.parametrize("staged", [False, True])
def test_patch_rejects_preexisting_unrelated_test_changes(workspace, staged):
    commit = workspace.commit()
    test_path = "src/test/java/example/HelloControllerTest.java"
    path = workspace.root / test_path
    path.write_text("// weakened test", encoding="utf-8")
    if staged:
        workspace.git("add", "--", test_path)
    proposal = PatchProposal(summary="fix", changes=[FileChange(path=EDITABLE_PATH,
        expected_sha256=file_digest(workspace.root / EDITABLE_PATH), content="new code")])
    original = (workspace.root / EDITABLE_PATH).read_bytes()
    with pytest.raises(PermissionError, match="候选范围外"):
        workspace.apply(proposal, attempt=1)
    assert workspace.commit() == commit
    assert (workspace.root / EDITABLE_PATH).read_bytes() == original
    assert path.read_text(encoding="utf-8") == "// weakened test"


@pytest.mark.ac("AC-25")
def test_archive_verifies_original_bytes_and_run_scope(tmp_path):
    archive = ArtifactArchive(tmp_path / "archive", InMemoryStore())
    artifact = archive.put(run_id="r", kind="SPEC", producer="test", value={"version": 1})
    assert archive.read(artifact.artifact_id, run_id="r") == {"version": 1}
    with pytest.raises(PermissionError):
        archive.read(artifact.artifact_id, run_id="other")
    Path(artifact.uri).write_text('{"version":2}', encoding="utf-8")
    with pytest.raises(ValueError):
        archive.read(artifact.artifact_id, run_id="r")


@pytest.mark.ac("AC-38")
@pytest.mark.parametrize("mode,expected", [("pass", "PASS"), ("missing", "INCONCLUSIVE"),
    ("skipped", "INCONCLUSIVE"), ("exit-mismatch", "INCONCLUSIVE"), ("fail", "FAIL")])
def test_executor_uses_junit_and_exit_status_instead_of_text(workspace, mode, expected):
    script = '''import pathlib,sys
root=pathlib.Path(sys.argv[1].split("=",1)[1]);root.mkdir(parents=True,exist_ok=True)
mode=MODE
if mode!="missing":
    child="<skipped/>" if mode=="skipped" else ("<failure/>" if mode=="fail" else "")
    (root/"TEST-evidence.xml").write_text('<testsuite><testcase name="required">'+child+'</testcase></testsuite>')
print("PASS")
sys.exit(1 if mode in {"fail","exit-mismatch"} else 0)
'''.replace("MODE", repr(mode))
    runner = SurefireRunner(argv=[sys.executable, "-c", script], environment=os.environ,
                            required_tests={"required"}, timeout=10)
    assert runner.run(workspace, attempt=1)["decision"] == expected
