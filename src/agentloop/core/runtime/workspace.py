"""单任务 Git 工作区与受限补丁。不是操作系统级沙箱。"""

import hashlib
import os
from pathlib import Path, PurePosixPath
import shutil
import subprocess

from ..contracts.delivery import PatchProposal


def file_digest(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


class GitWorkspace:
    def __init__(self, root, *, editable_paths):
        self.root = Path(root).resolve()
        self.editable_paths = frozenset(editable_paths)
        if not (self.root / ".agentloop-owned").is_file():
            raise ValueError("只能操作 AgentLoop 专属工作区")

    @classmethod
    def from_fixture(cls, fixture, root, *, editable_paths):
        fixture, root = Path(fixture).resolve(), Path(root).resolve()
        if not root.exists():
            shutil.copytree(fixture, root, ignore=shutil.ignore_patterns("target", ".git"))
            (root / ".agentloop-owned").write_text("Phase 1 isolated fixture\n", encoding="utf-8")
            instance = cls(root, editable_paths=editable_paths)
            instance.git("init")
            instance.git("add", ".")
            instance.git("commit", "-m", "fixture baseline")
        return cls(root, editable_paths=editable_paths)

    def git(self, *args):
        result = subprocess.run(["git", "-c", "core.hooksPath=NUL" if os.name == "nt" else "core.hooksPath=/dev/null",
            "-c", "user.name=AgentLoop", "-c", "user.email=agentloop@example.invalid", *args], cwd=self.root,
            capture_output=True, text=True, encoding="utf-8", errors="replace", timeout=30, check=True)
        return result.stdout.strip()

    def commit(self):
        return self.git("rev-parse", "HEAD")

    def assert_revision(self, commit):
        if self.commit() != commit or self.git("status", "--porcelain", "--untracked-files=all"):
            raise ValueError("工作区 Commit、受跟踪文件或未跟踪输入已改变，原证据不可复用")

    def protected_digest(self):
        parts = []
        for path in sorted(self.root.rglob("*")):
            rel = path.relative_to(self.root).as_posix()
            if path.is_file() and (rel.startswith("src/test/") or rel == "pom.xml"):
                parts.append(rel + ":" + file_digest(path))
        return hashlib.sha256("\n".join(parts).encode()).hexdigest()

    def apply(self, proposal: PatchProposal, *, attempt):
        checked = []
        seen = set()
        for change in proposal.changes:
            rel = PurePosixPath(change.path)
            if (rel.is_absolute() or ".." in rel.parts or "\\" in change.path or ":" in change.path
                    or change.path not in self.editable_paths or change.path in seen):
                raise PermissionError(f"不允许修改 {change.path}")
            seen.add(change.path)
            path = self.root.joinpath(*rel.parts)
            if not path.resolve().is_relative_to(self.root) or any(p.is_symlink() for p in [path, *path.parents]):
                raise PermissionError("路径包含链接或越界")
            current = file_digest(path)
            desired = hashlib.sha256(change.content.encode("utf-8")).hexdigest()
            if current not in {change.expected_sha256, desired}:
                raise ValueError("补丁输入版本冲突")
            checked.append((path, change.content))
        # 恢复允许候选文件已经写入；其他受跟踪变更不能被夹带进本次提交。
        dirty = set(self.git("diff", "HEAD", "--name-only").splitlines())
        staged = set(self.git("diff", "--cached", "--name-only").splitlines())
        if (dirty | staged) - seen:
            raise PermissionError("工作区包含候选范围外的未提交变更")
        untracked = set(self.git("ls-files", "--others", "--exclude-standard").splitlines())
        if untracked - {path + ".agentloop-tmp" for path in seen}:
            raise PermissionError("工作区包含未经审查的未跟踪文件")
        protected = self.protected_digest()
        for path, content in checked:
            temporary = path.with_name(path.name + ".agentloop-tmp")
            temporary.write_text(content, encoding="utf-8", newline="")
            os.replace(temporary, path)
        if self.protected_digest() != protected:
            raise ValueError("补丁修改了受保护的测试或构建配置")
        self.git("add", "--", *[c.path for c in proposal.changes])
        if self.git("diff", "--cached", "--name-only"):
            self.git("commit", "-m", f"backend candidate {attempt}")
        return self.commit()
