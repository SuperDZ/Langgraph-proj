"""可查询、幂等的实际部署后端；本地后端运行真实回环 HTTP 服务。"""

import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import sqlite3
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib import request, error
from urllib.parse import unquote
from ..contracts.phase3 import DeploymentObservation
from .configuration import resolve_secret
from ...knowledge.archive import canonical


def bundle_digest(bundle):
    return hashlib.sha256(canonical(bundle).encode()).hexdigest()


def validate_bundle(bundle, expected):
    if bundle_digest(bundle) != expected or set(bundle) != {"files", "commit"}:
        raise ValueError("部署包摘要或结构不正确")
    files = bundle["files"]
    if not isinstance(files, dict) or not files or len(files) > 100:
        raise ValueError("部署文件清单无效")
    total = 0
    for name, content in files.items():
        path = PurePosixPath(name)
        if path.is_absolute() or ".." in path.parts or "\\" in name or ":" in name or not isinstance(content, str):
            raise ValueError("部署文件路径或内容无效")
        total += len(content.encode())
    if total > 2_000_000 or "index.html" not in files:
        raise ValueError("部署包过大或缺少首页")


class LocalStaticProvider:
    """只发布文本静态资源，不执行包内脚本/命令；持久状态可在重启后对账。"""
    def __init__(self, root, target):
        self.root, self.target = Path(root).resolve(), target
        marker = self.root / ".agentloop-target"
        if self.root.exists() and any(self.root.iterdir()) and not marker.is_file():
            raise PermissionError("目标目录不属于 AgentLoop")
        self.root.mkdir(parents=True, exist_ok=True)
        identity = canonical({"project": target.project_id, "target": target.target_id, "environment": target.environment})
        if marker.exists() and marker.read_text() != identity:
            raise PermissionError("目标目录已绑定其他环境/项目")
        marker.write_text(identity)
        self.lock = threading.RLock()
        self.db = sqlite3.connect(self.root / "target.db", isolation_level=None, check_same_thread=False)
        self.db.execute("PRAGMA busy_timeout=10000")
        self.db.executescript("CREATE TABLE IF NOT EXISTS state(k TEXT PRIMARY KEY,v TEXT NOT NULL); CREATE TABLE IF NOT EXISTS operations(id TEXT PRIMARY KEY,v TEXT NOT NULL);")
        baseline = {"files": {"index.html": "<!doctype html><title>AgentLoop baseline</title>AgentLoop baseline"}, "commit": "baseline"}
        digest = bundle_digest(baseline)
        self._save_bundle(baseline, digest)
        self.db.execute("INSERT OR IGNORE INTO state VALUES('current',?)", (digest,))
        provider = self
        class Handler(BaseHTTPRequestHandler):
            def log_message(self, *args):
                pass
            def do_GET(self):
                path = PurePosixPath(unquote(self.path.split("?", 1)[0]).lstrip("/")).as_posix()
                if ".." in PurePosixPath(path).parts or "\\" in path:
                    self.send_error(403); return
                with provider.lock:
                    bundle = provider._load_bundle(provider.current())
                content = bundle["files"].get("index.html" if path in {"", "."} else path)
                if content is None:
                    self.send_error(404); return
                raw = content.encode()
                self.send_response(200)
                self.send_header("Content-Type", "text/html; charset=utf-8")
                self.send_header("Content-Length", str(len(raw)))
                self.end_headers(); self.wfile.write(raw)
        self.server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        self.thread = threading.Thread(target=self.server.serve_forever, daemon=True)
        self.thread.start()

    def current(self):
        with self.lock:
            return self.db.execute("SELECT v FROM state WHERE k='current'").fetchone()[0]

    def _save_bundle(self, bundle, digest):
        validate_bundle(bundle, digest)
        path = self.root / (digest + ".json")
        raw = canonical(bundle).encode()
        if not path.exists():
            try:
                with path.open("xb") as stream:
                    stream.write(raw); stream.flush(); os.fsync(stream.fileno())
            except FileExistsError:
                pass
        if path.read_bytes() != raw:
            raise ValueError("部署包持久内容已损坏")

    def _load_bundle(self, digest):
        bundle = json.loads((self.root / (digest + ".json")).read_text(encoding="utf-8"))
        validate_bundle(bundle, digest)
        return bundle

    def execute(self, operation_id, action, *, bundle, artifact_digest, previous_digest=None):
        with self.lock:
            self.db.execute("BEGIN IMMEDIATE")
            try:
                params = bundle_digest({"action": action, "artifact_digest": artifact_digest, "previous_digest": previous_digest})
                row = self.db.execute("SELECT v FROM operations WHERE id=?", (operation_id,)).fetchone()
                if row:
                    stored = json.loads(row[0])
                    if stored["params"] != params:
                        raise ValueError("外部操作幂等键冲突")
                    result = DeploymentObservation.model_validate(stored["observation"])
                else:
                    old = self.current()
                    if action == "DEPLOY":
                        self._save_bundle(bundle, artifact_digest)
                        desired = artifact_digest
                    elif action == "ROLLBACK" and previous_digest:
                        self._load_bundle(previous_digest)
                        if old not in {artifact_digest, previous_digest}:
                            raise ValueError("目标已被其他部署修改，不能覆盖")
                        desired = previous_digest
                    else:
                        raise ValueError("不支持的部署操作")
                    self.db.execute("UPDATE state SET v=? WHERE k='current'", (desired,))
                    result = DeploymentObservation(operation_id=operation_id, status="SUCCEEDED", artifact_digest=desired,
                        previous_digest=old if action == "DEPLOY" else previous_digest, evidence="durable target pointer and HTTP service")
                    self.db.execute("INSERT INTO operations VALUES(?,?)", (operation_id, canonical({"params": params, "observation": result.model_dump(mode="json")})))
                self.db.execute("COMMIT")
            except BaseException:
                self.db.execute("ROLLBACK"); raise
        return result

    def query(self, operation_id):
        with self.lock:
            row = self.db.execute("SELECT v FROM operations WHERE id=?", (operation_id,)).fetchone()
        return DeploymentObservation.model_validate(json.loads(row[0])["observation"]) if row else DeploymentObservation(operation_id=operation_id, status="NOT_FOUND")

    def health(self, expected_digest):
        with self.lock:
            before = self.current()
            bundle = self._load_bundle(before)
        try:
            with request.urlopen(f"http://127.0.0.1:{self.server.server_port}{self.target.health_path}", timeout=self.target.timeout_seconds) as response:
                raw = response.read(2_000_001)
                expected = bundle["files"].get(self.target.health_path.lstrip("/"), "").encode()
                passed = (response.status == 200 and raw == expected and self.target.expected_text.encode() in raw
                          and before == expected_digest and self.current() == before)
        except (OSError, error.URLError):
            passed = False
        return {"artifact_digest": before, "healthy": passed, "evidence": f"HTTP GET {self.target.health_path}; exact body and active digest checked"}

    def cancel(self, operation_id):
        # 已经原子发布的本地操作不能伪装撤销；调用方必须走授权回滚。
        return self.query(operation_id)

    def close(self):
        self.server.shutdown(); self.server.server_close(); self.thread.join(timeout=2)
        self.db.close()


class HTTPDeploymentProvider:
    """独立部署代理协议。写请求不自动重试，未知结果仅通过查询对账。"""
    def __init__(self, target):
        self.target = target
        class NoRedirect(request.HTTPRedirectHandler):
            def redirect_request(self, *args, **kwargs): return None
        self.opener = request.build_opener(NoRedirect())

    def _request(self, path, payload=None):
        raw = canonical(payload).encode() if payload is not None else None
        req = request.Request(self.target.endpoint.rstrip("/") + path, data=raw,
            headers={"Content-Type": "application/json", "Authorization": "Bearer " + resolve_secret(self.target.secret_ref)})
        with self.opener.open(req, timeout=self.target.timeout_seconds) as response:
            data = response.read(3_000_001)
            if len(data) > 3_000_000: raise ValueError("部署代理响应过大")
            return json.loads(data)

    def execute(self, operation_id, action, *, bundle, artifact_digest, previous_digest=None):
        result = self._request("/operations", {"operation_id": operation_id, "action": action,
            "target_id": self.target.target_id, "project_id": self.target.project_id,
            "artifact_digest": artifact_digest, "previous_digest": previous_digest, "bundle": bundle})
        return DeploymentObservation.model_validate(result)

    def query(self, operation_id):
        return DeploymentObservation.model_validate(self._request("/operations/" + operation_id))

    def health(self, expected_digest):
        return self._request("/health", {"expected_digest": expected_digest})

    def cancel(self, operation_id):
        return DeploymentObservation.model_validate(self._request("/operations/" + operation_id + "/cancel", {}))

    def close(self): pass
