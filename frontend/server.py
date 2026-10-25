"""AGENTLOOP 工作台本地服务。

把 phase1 交付流程的人工介入点（启动、G1 确认、模拟发布授权、
BLOCKED 恢复、证据导出）暴露为 HTTP API，供前端工作台页面调用。

仅监听本机回环地址；身份沿用本地 demo RBAC（demo-owner），
不代表外部认证。启动示例见文件末尾 docstring。

    python frontend/server.py \
        --java-home .agentloop/toolchains/jdk-21.0.12.1+1 \
        --maven "E:/CodeEnv/Java/Maven/binary/apache-maven-3.9.16/bin/mvn.cmd"
"""

import argparse
import json
import re
import shutil
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse, parse_qs

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from agentloop.examples.demo import build_demo          # noqa: E402
from agentloop.core.contracts.enums import RunStatus    # noqa: E402

DEFAULT_TASK = "修复 /hello 的缺失、空串和空白参数错误，保留合法参数行为。"
RUN_ID_RE = re.compile(r"^[A-Za-z0-9_-]{1,80}$")
BOUNDARY = ("Workbench live run. Scripted role outputs; real local Maven/Spring tests; "
            "simulated deployment only; demo human identity; not production evidence.")


class JobBusy(RuntimeError):
    pass


class Workbench:
    """按 run_id 惰性装配工作流；同一时刻只允许一个作业在执行。"""

    def __init__(self, data_dir, java_home=None, maven=None):
        self.data_dir = Path(data_dir).resolve()
        self.workflows = {}
        self.tasks = {}
        self.lock = threading.Lock()
        self.job = {"busy": False, "run_id": None, "kind": None, "error": None}
        self.java_home, self.maven = java_home, maven
        self._state_cache = {}

    # ---------------- 工作流装配 ----------------

    def _wf(self, run_id):
        wf = self.workflows.get(run_id)
        if wf is None:
            wf = build_demo(data_dir=self.data_dir / "runs", run_id=run_id,
                            java_home=self.java_home, maven=self.maven)
            self.workflows[run_id] = wf
        return wf

    def _job_snapshot(self):
        return {k: self.job[k] for k in ("busy", "run_id", "kind", "error")}

    # ---------------- 作业执行 ----------------

    def dispatch(self, run_id, kind, fn):
        with self.lock:
            if self.job["busy"]:
                raise JobBusy("已有作业在执行（" + str(self.job["run_id"]) + "），请稍候")
            self.job.update(busy=True, run_id=run_id, kind=kind, error=None)

        def worker():
            try:
                fn()
                self.job["error"] = None
            except Exception as exc:                      # noqa: BLE001
                self.job["error"] = f"{type(exc).__name__}: {exc}"
            finally:
                self.job["busy"] = False

        threading.Thread(target=worker, daemon=True).start()

    def start(self, run_id, task, require_confirmation=False, security_example=False):
        def fn():
            wf = self._wf(run_id)
            self.tasks[run_id] = task or DEFAULT_TASK
            wf.config.require_confirmation = bool(require_confirmation)
            wf.start(run_id, self.tasks[run_id])
        self.dispatch(run_id, "start", fn)

    def confirm_g1(self, run_id):
        def fn():
            self._wf(run_id).confirm_g1(run_id, "demo-owner")
        self.dispatch(run_id, "confirm_g1", fn)

    def authorize(self, run_id):
        def fn():
            self._wf(run_id).authorize_simulation(run_id, "demo-owner")
        self.dispatch(run_id, "authorize", fn)

    def resume(self, run_id):
        def fn():
            wf = self._wf(run_id)
            run = wf.store.get_run(run_id)
            if run.status is RunStatus.BLOCKED:
                wf.transitions.transition(run_id, target_status=RunStatus.RUNNING,
                                          expected_version=run.state_version)
            wf.start(run_id, self.tasks.get(run_id, DEFAULT_TASK))
        self.dispatch(run_id, "resume", fn)

    # ---------------- 状态与导出 ----------------

    def actions_for(self, summary):
        phase, status = summary.get("phase"), summary.get("status")
        return {
            "confirm_g1": phase == "G1" and status == "WAITING_APPROVAL",
            "authorize": phase == "RELEASE_AUTHORIZATION" and status == "WAITING_APPROVAL",
            "resume": status == "BLOCKED",
        }

    def state(self, run_id):
        try:
            wf = self._wf(run_id)
            summary = wf.summary(run_id)
            events = [e.model_dump(mode="json") for e in wf.store.events_for(run_id)]
            artifacts = [{"metadata": a.model_dump(mode="json")} for a in wf.store.artifacts_for(run_id)]
            state = {"exists": True, "summary": summary, "events": events,
                     "artifacts": artifacts, "job": self._job_snapshot(),
                     "actions": self.actions_for(summary),
                     "boundary": "实时工作台运行：脚本化角色输出 + 真实本地 Maven 测试 + 模拟发布。"}
            self._state_cache[run_id] = state
            return state
        except Exception:                                 # noqa: BLE001
            # 作业执行中 checkpoint 可能短暂锁定：返回上次缓存
            cached = self._state_cache.get(run_id)
            if cached:
                stale = dict(cached)
                stale["stale"] = True
                return stale
            return {"exists": False, "job": self._job_snapshot(), "actions": {},
                    "boundary": "", "events": [], "artifacts": []}

    def export(self, run_id):
        wf = self._wf(run_id)
        artifacts = wf.store.artifacts_for(run_id)
        return {"summary": wf.summary(run_id), "evidence_boundary": BOUNDARY,
                "artifacts": [{"metadata": a.model_dump(mode="json"),
                               "body": wf.archive.read(a.artifact_id, run_id=run_id)}
                              for a in artifacts],
                "events": [e.model_dump(mode="json") for e in wf.store.events_for(run_id)]}


class Handler(BaseHTTPRequestHandler):
    bench: Workbench = None
    static_dir: Path = None
    server_version = "AgentLoopWorkbench/0.1"

    # ---------------- 基础输出 ----------------

    def _json(self, payload, status=200, download=None):
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        if download:
            self.send_header("Content-Disposition",
                             f'attachment; filename="{download}"')
        self.end_headers()
        self.wfile.write(body)

    def _static(self, rel):
        target = (self.static_dir / rel).resolve()
        if not str(target).startswith(str(self.static_dir.resolve())) or not target.is_file():
            self._json({"error": "not found"}, 404)
            return
        kinds = {".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8",
                 ".css": "text/css; charset=utf-8", ".json": "application/json"}
        body = target.read_bytes()
        self.send_response(200)
        self.send_header("Content-Type", kinds.get(target.suffix, "application/octet-stream"))
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, fmt, *args):                    # noqa: A003
        pass                                              # 静默访问日志

    # ---------------- 路由 ----------------

    def do_GET(self):                                     # noqa: N802
        url = urlparse(self.path)
        if url.path in ("/", "/index.html"):
            self._static("index.html")
        elif url.path == "/api/hello":
            self._json({"ok": True, "service": "agentloop-workbench"})
        elif url.path == "/api/state":
            run_id = (parse_qs(url.query).get("run_id") or [""])[0]
            if not RUN_ID_RE.fullmatch(run_id):
                self._json({"error": "run_id 只能包含字母、数字、下划线和连字符"}, 400)
                return
            self._json(self.bench.state(run_id))
        elif url.path == "/api/export":
            run_id = (parse_qs(url.query).get("run_id") or [""])[0]
            if not RUN_ID_RE.fullmatch(run_id):
                self._json({"error": "非法 run_id"}, 400)
                return
            try:
                self._json(self.bench.export(run_id), download=f"{run_id}-evidence.json")
            except Exception as exc:                      # noqa: BLE001
                self._json({"error": str(exc)}, 500)
        else:
            self._json({"error": "not found"}, 404)

    def do_POST(self):                                    # noqa: N802
        url = urlparse(self.path)
        length = int(self.headers.get("Content-Length") or 0)
        try:
            body = json.loads(self.rfile.read(length) or b"{}")
        except json.JSONDecodeError:
            self._json({"error": "请求体不是合法 JSON"}, 400)
            return
        run_id = str(body.get("run_id") or "")
        if not RUN_ID_RE.fullmatch(run_id):
            self._json({"error": "run_id 只能包含字母、数字、下划线和连字符"}, 400)
            return
        try:
            if url.path == "/api/start":
                self.bench.start(run_id, str(body.get("task") or DEFAULT_TASK),
                                 require_confirmation=bool(body.get("require_confirmation")),
                                 security_example=bool(body.get("security_example")))
                self._json({"ok": True, "dispatched": "start"})
            elif url.path == "/api/confirm_g1":
                self.bench.confirm_g1(run_id)
                self._json({"ok": True, "dispatched": "confirm_g1"})
            elif url.path == "/api/authorize":
                self.bench.authorize(run_id)
                self._json({"ok": True, "dispatched": "authorize"})
            elif url.path == "/api/resume":
                self.bench.resume(run_id)
                self._json({"ok": True, "dispatched": "resume"})
            else:
                self._json({"error": "not found"}, 404)
        except JobBusy as exc:
            self._json({"error": str(exc)}, 409)
        except Exception as exc:                          # noqa: BLE001
            self._json({"error": f"{type(exc).__name__}: {exc}"}, 500)


def main():
    parser = argparse.ArgumentParser(description="AGENTLOOP 工作台本地服务（仅回环地址）")
    parser.add_argument("--port", type=int, default=8438)
    parser.add_argument("--data-dir", type=Path, default=ROOT / ".agentloop" / "workbench")
    parser.add_argument("--java-home")
    parser.add_argument("--maven")
    args = parser.parse_args()

    Handler.bench = Workbench(args.data_dir, java_home=args.java_home, maven=args.maven)
    Handler.static_dir = ROOT / "frontend"
    server = ThreadingHTTPServer(("127.0.0.1", args.port), Handler)
    print(f"工作台服务已启动: http://127.0.0.1:{args.port}/  (Ctrl+C 停止)", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        for wf in Handler.bench.workflows.values():
            wf.close()
            wf.store.close()
        server.server_close()


if __name__ == "__main__":
    main()
