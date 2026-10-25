"""Skills 隔离导入、人工批准/绑定、版本锁定。导入期间绝不执行脚本。"""

import base64
import difflib
import io
import json
from pathlib import Path, PurePosixPath
import re
import stat
import subprocess
import tempfile
from urllib import request
from urllib.parse import urlparse
import zipfile
import tarfile
import yaml
from .configuration import digest


MAX_BYTES = 2_000_000


def safe_member(name):
    path = PurePosixPath(name)
    if "\\" in name or ":" in name or path.is_absolute() or ".." in path.parts or not path.parts:
        raise ValueError("Skill 包含不安全路径")
    return path.as_posix()


class SkillRegistry:
    def __init__(self, repository, rbac, *, trusted_hosts=()):
        self.repo, self.store, self.rbac = repository, repository.store, rbac
        self.trusted_hosts = frozenset(trusted_hosts)

    def _owner(self, principal, project):
        self.rbac.require_human(principal)
        self.rbac.require_role(principal, "project_owner", project)

    def import_directory(self, run_id, directory, *, source=None):
        supplied = Path(directory)
        if supplied.is_symlink() or getattr(supplied, "is_junction", lambda: False)():
            raise ValueError("Skill 根目录不能为链接")
        root = supplied.resolve()
        files = {}
        total = 0
        for path in sorted(root.rglob("*")):
            if path.is_symlink() or getattr(path, "is_junction", lambda: False)():
                raise ValueError("Skill 不允许符号链接或目录联接")
            if path.is_file():
                if len(files) >= 200 or path.stat().st_size + total > MAX_BYTES:
                    raise ValueError("Skill 大小或文件数量超过隔离上限")
                data = path.read_bytes()
                total += len(data)
                files[safe_member(path.relative_to(root).as_posix())] = data
        return self._quarantine(run_id, files, source or {"kind": "directory", "name": root.name}, expected_name=root.name)

    def import_archive(self, run_id, filename, *, source=None):
        path = Path(filename)
        if path.stat().st_size > MAX_BYTES:
            raise ValueError("Skill 压缩包过大")
        files, total = {}, 0
        def add(name, data):
            nonlocal total
            name = safe_member(name)
            total += len(data)
            if name in files or total > MAX_BYTES or len(files) >= 200:
                raise ValueError("Skill 重复路径、数量或展开大小超限")
            files[name] = data
        if zipfile.is_zipfile(path):
            with zipfile.ZipFile(path) as bundle:
                for member in bundle.infolist():
                    if stat.S_ISLNK(member.external_attr >> 16):
                        raise ValueError("Skill 压缩包不能含链接")
                    safe_member(member.filename)
                    if not member.is_dir():
                        if member.file_size > MAX_BYTES - total:
                            raise ValueError("Skill 解压上限")
                        add(member.filename, bundle.read(member))
        else:
            with tarfile.open(path) as bundle:
                for member in bundle:
                    safe_member(member.name)
                    if member.isdir():
                        continue
                    if not member.isfile() or member.size > MAX_BYTES - total:
                        raise ValueError("Skill 归档包含链接/特殊文件或过大")
                    add(member.name, bundle.extractfile(member).read(MAX_BYTES + 1))
        if "SKILL.md" not in files:
            prefixes = {name.split("/")[0] for name in files}
            if len(prefixes) == 1:
                prefix = prefixes.pop() + "/"
                files = {k[len(prefix):]: v for k, v in files.items()}
        return self._quarantine(run_id, files, source or {"kind": "archive", "name": path.name})

    def download(self, run_id, url, expected_sha256):
        parsed = urlparse(url)
        if (parsed.scheme != "https" or parsed.hostname not in self.trusted_hosts or parsed.username
                or parsed.password or parsed.query or parsed.fragment):
            raise ValueError("Skill 下载源不在受信 HTTPS registry 清单")
        class NoRedirect(request.HTTPRedirectHandler):
            def redirect_request(self, *args, **kwargs):
                return None
        with request.build_opener(NoRedirect()).open(url, timeout=30) as response:
            data = response.read(MAX_BYTES + 1)
        import hashlib
        if len(data) > MAX_BYTES or hashlib.sha256(data).hexdigest() != expected_sha256:
            raise ValueError("下载 Skill 的大小或 SHA256 不符")
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / "skill.bundle"
            path.write_bytes(data)
            return self.import_archive(run_id, path, source={"kind": "registry", "url": url, "sha256": expected_sha256})

    def import_git(self, run_id, url, revision, *, principal_id):
        project = self.store.get_run(run_id).project_id
        self._owner(principal_id, project)
        parsed = urlparse(url)
        if parsed.scheme != "https" or parsed.hostname not in self.trusted_hosts or parsed.username or parsed.query or parsed.fragment:
            raise ValueError("Git Skill 来源未授权")
        if not re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9._/-]{0,150}", revision) or ".." in revision:
            raise ValueError("Git revision 无效")
        with tempfile.TemporaryDirectory() as temp:
            root = Path(temp) / "repo"
            def git(*args):
                result = subprocess.run(["git", "-c", "core.hooksPath=NUL" if __import__('os').name == 'nt' else "core.hooksPath=/dev/null",
                    "-c", "protocol.file.allow=never", "-c", "http.followRedirects=false", *args],
                    capture_output=True, timeout=60, check=False, env={k: v for k, v in __import__('os').environ.items()
                        if k.upper() in {"PATH", "SYSTEMROOT", "WINDIR", "TEMP", "TMP", "COMSPEC"}})
                if result.returncode:
                    raise ValueError("Git Skill 获取失败")
                return result.stdout.decode().strip()
            git("clone", "--no-checkout", "--no-recurse-submodules", url, str(root))
            commit = git("-C", str(root), "rev-parse", "--verify", revision + "^{commit}")
            # git archive 不执行所获取仓库中的 hooks / scripts。
            bundle = Path(temp) / "skill.zip"
            git("-C", str(root), "archive", "--format=zip", "-o", str(bundle), commit)
            return self.import_archive(run_id, bundle, source={"kind": "git", "url": url, "revision": revision, "commit": commit})

    def _quarantine(self, run_id, files, source, expected_name=None):
        if "SKILL.md" not in files:
            raise ValueError("Skill 必须包含 SKILL.md")
        text = files["SKILL.md"].decode("utf-8")
        parts = text.split("---", 2)
        if len(parts) != 3 or parts[0].strip():
            raise ValueError("SKILL.md 缺少 YAML frontmatter")
        metadata = yaml.safe_load(parts[1])
        if not isinstance(metadata, dict) or not isinstance(metadata.get("name"), str):
            raise ValueError("Skill metadata 无效")
        name = metadata["name"]
        if not re.fullmatch(r"[a-z0-9]+(?:-[a-z0-9]+)*", name) or len(name) > 64 or (expected_name and name != expected_name):
            raise ValueError("Skill name 无效或与目录名不一致")
        description = metadata.get("description")
        if not isinstance(description, str) or not 1 <= len(description.strip()) <= 1024:
            raise ValueError("Skill 必须提供 description")
        encoded = {k: base64.b64encode(v).decode() for k, v in sorted(files.items())}
        version = digest(encoded)
        risks = []
        if any(k.startswith("scripts/") for k in files):
            risks.append("CONTAINS_SCRIPTS_NEVER_EXECUTED")
        if not metadata.get("license") and not any(k.upper().startswith("LICENSE") for k in files):
            risks.append("LICENSE_UNDECLARED")
        if any(word in text.lower() for word in ("skip g2", "ignore previous", "泄露", "跳过门禁", "approve memory")):
            risks.append("POSSIBLE_PROMPT_INJECTION")
        dependencies = []
        if "dependencies.json" in files:
            dependencies = json.loads(files["dependencies.json"])
            if not isinstance(dependencies, list) or any(not isinstance(x, str) for x in dependencies):
                raise ValueError("依赖清单必须为 Skill 内容哈希列表")
        with self.store.transaction():
            existing = self.store.runtime_get("skill", version)
            if existing:
                return existing
            artifact = self.repo.archive.put(run_id=run_id, kind="QUARANTINED_SKILL", producer="skill-import",
                value={"files": encoded, "metadata": metadata, "source": source, "risks": risks})
            record = {"hash": version, "name": name, "description": description, "artifact_id": artifact.artifact_id,
                "source_run": run_id, "source": source, "risks": risks, "dependencies": dependencies, "status": "QUARANTINED"}
            self.store.runtime_put("skill", version, record)
            self.repo.audit(run_id, "SKILL_QUARANTINED", {k: v for k, v in record.items() if k != "description"})
            return record

    def approve(self, version, *, principal_id, project_id, accepted_risks):
        self._owner(principal_id, project_id)
        with self.store.transaction():
            record = self.store.runtime_get("skill", version)
            if not record or record["status"] not in {"QUARANTINED", "APPROVED"}:
                raise ValueError("Skill 版本不存在或已停用")
            if set(accepted_risks) != set(record["risks"]):
                raise ValueError("必须明确确认当前全部风险")
            for dep in record["dependencies"]:
                child = self.store.runtime_get("skill", dep)
                if not child or child["status"] != "APPROVED":
                    raise ValueError("Skill 依赖尚未批准")
            approval = {"project": project_id, "hash": version, "principal_id": principal_id, "risks": accepted_risks}
            self.store.runtime_put("skill_approval", f"{project_id}/{version}", approval)
            record["status"] = "APPROVED"
            self.store.runtime_put("skill", version, record)
            self.repo.audit(record["source_run"], "SKILL_APPROVED", approval)

    def bind(self, version, *, principal_id, project_id, role):
        self._owner(principal_id, project_id)
        with self.store.transaction():
            record = self.store.runtime_get("skill", version)
            if not record or record["status"] != "APPROVED" or not self.store.runtime_get("skill_approval", f"{project_id}/{version}"):
                raise ValueError("Skill 未获得项目人工批准")
            binding = {"project": project_id, "role": role, "hash": version, "principal_id": principal_id}
            self.store.runtime_put("skill_binding", f"{project_id}/{role}/{version}", binding)
            self.repo.audit(record["source_run"], "SKILL_BOUND", binding)

    def load_for(self, run_id, config):
        project = self.store.get_run(run_id).project_id
        result = []
        for name, version in config.skills.items():
            record = self.store.runtime_get("skill", version)
            if not record or record["name"] != name or record["status"] != "APPROVED":
                raise PermissionError("Skill 不存在、版本不匹配或已停用")
            if not self.store.runtime_get("skill_binding", f"{project}/{config.role}/{version}"):
                raise PermissionError("Skill 尚未人工绑定该角色")
            body = self.repo.archive.read(record["artifact_id"], run_id=record["source_run"])
            if digest(body["files"]) != version:
                raise ValueError("Skill 内容哈希不匹配")
            result.append({"name": name, "hash": version, "untrusted_text": base64.b64decode(body["files"]["SKILL.md"]).decode()})
        return result

    def read_reference(self, run_id, config, name, path):
        self.load_for(run_id, config)
        path = safe_member(path)
        if not path.startswith(("references/", "assets/")):
            raise PermissionError("仅允许按需读取 references/assets；scripts 必须经过独立执行器")
        record = self.store.runtime_get("skill", config.skills[name])
        body = self.repo.archive.read(record["artifact_id"], run_id=record["source_run"])
        return base64.b64decode(body["files"][path])

    def set_status(self, version, status, *, principal_id, project_id):
        self._owner(principal_id, project_id)
        if status not in {"DISABLED", "UNINSTALLED"}:
            raise ValueError("无效 Skill 生命周期操作")
        record = self.store.runtime_get("skill", version)
        # 跨项目批准不能被其他项目负责人全局撤销。
        origin_project = self.store.get_run(record["source_run"]).project_id
        if project_id != origin_project:
            raise PermissionError("只有来源项目负责人可以停用该包")
        record["status"] = status
        self.store.runtime_put("skill", version, record)
        self.repo.audit(record["source_run"], "SKILL_" + status, {"hash": version, "principal_id": principal_id})

    def list(self, query=""):
        return [{k: v for k, v in r.items() if k != "artifact_id"} for r in self.store.runtime_list("skill")
                if query.lower() in (r["name"] + r["description"]).lower()]

    def export(self, version, destination):
        record = self.store.runtime_get("skill", version)
        body = self.repo.archive.read(record["artifact_id"], run_id=record["source_run"])
        with zipfile.ZipFile(destination, "x", compression=zipfile.ZIP_DEFLATED) as bundle:
            for path, value in body["files"].items():
                bundle.writestr(path, base64.b64decode(value))

    def compare(self, before, after):
        def body(version):
            record = self.store.runtime_get("skill", version)
            return self.repo.archive.read(record["artifact_id"], run_id=record["source_run"])["files"]
        a, b = body(before), body(after)
        return {path: "\n".join(difflib.unified_diff(base64.b64decode(a.get(path, "")).decode(errors="replace").splitlines(),
            base64.b64decode(b.get(path, "")).decode(errors="replace").splitlines()))
            for path in sorted(set(a) | set(b)) if a.get(path) != b.get(path)}
