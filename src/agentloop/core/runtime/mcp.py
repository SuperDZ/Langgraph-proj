"""MCP 2025-11-25 客户端与确定性工具代理。服务端文字没有授权效力。"""

import json
import hashlib
import os
from pathlib import Path
import queue
import re
import subprocess
import threading
import time
from urllib import request
from urllib.parse import urlparse
from uuid import uuid4
from datetime import timedelta
from pydantic import Field, model_validator
from jsonschema import Draft202012Validator, SchemaError
from referencing import Registry
from ..contracts.models import StrictModel, utc_now
from ..approvals.rbac import CAPABILITY_REGISTRY
from .configuration import digest, resolve_secret


PROTOCOL = "2025-11-25"
MAX_MESSAGE = 2_000_000
INDEPENDENT_EXECUTOR_CAPABILITIES = frozenset({"cap.deploy.production", "cap.deploy.staging", "cap.secrets.manage", "cap.memory.review"})


def sanitized_review(value, secrets):
    """保留可审查的参数结构；凭据内容和敏感字段值不能进入审批记录。"""
    if isinstance(value, str):
        for secret in secrets:
            value = value.replace(secret, "[REDACTED]")
        return value
    if isinstance(value, dict):
        return {sanitized_review(key, secrets): "[REDACTED]" if re.search(r"token|password|passwd|secret|api[_-]?key|authorization", key, re.I)
                else sanitized_review(item, secrets) for key, item in value.items()}
    if isinstance(value, list):
        return [sanitized_review(item, secrets) for item in value]
    return value


class ToolPolicy(StrictModel):
    capability: str
    mutating: bool = True
    path_parameters: list[str] = Field(default_factory=list)
    url_parameters: list[str] = Field(default_factory=list)


class ToolRequest(StrictModel):
    server_id: str
    tool_name: str
    arguments: dict


class ServerConfig(StrictModel):
    server_id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,80}$")
    transport: str
    command: list[str] = Field(default_factory=list)
    cwd: str | None = None
    env_refs: dict[str, str] = Field(default_factory=dict)
    url: str | None = None
    auth_ref: str | None = None
    timeout: float = Field(default=20, gt=0, le=120)
    tools: dict[str, ToolPolicy]
    pinned_files: list[str] = Field(default_factory=list)

    @model_validator(mode="after")
    def safe_registration(self):
        refs = list(self.env_refs.values()) + ([self.auth_ref] if self.auth_ref else [])
        if any(not re.fullmatch(r"env:[A-Z][A-Z0-9_]{0,100}", ref) for ref in refs):
            raise ValueError("MCP 凭据只能使用 env:NAME 引用")
        if any(not re.fullmatch(r"[A-Za-z_][A-Za-z0-9_]*", key) for key in self.env_refs):
            raise ValueError("MCP 环境变量名称无效")
        if any(not Path(path).is_absolute() for path in self.pinned_files):
            raise ValueError("MCP pinned_files 必须为绝对路径")
        if self.transport == "http":
            parsed = urlparse(self.url or "")
            if (parsed.scheme != "https" and not (parsed.scheme == "http" and parsed.hostname in {"127.0.0.1", "::1", "localhost"})) or not parsed.hostname or parsed.username or parsed.password or parsed.query or parsed.fragment:
                raise ValueError("MCP URL 必须为无凭据的 HTTPS 或本机 HTTP")
        elif self.transport == "stdio":
            if not self.command or not Path(self.command[0]).is_absolute():
                raise ValueError("MCP stdio command 必须为绝对路径")
        else:
            raise ValueError("不支持的 MCP transport")
        return self


def validate_schema(schema):
    # 禁止远端 $ref 触发额外网络请求；仅使用本地文档引用。
    def walk(value):
        if isinstance(value, dict):
            for key, item in value.items():
                if key in {"$ref", "$dynamicRef"} and (not isinstance(item, str) or not item.startswith("#")):
                    raise ValueError("工具 Schema 仅支持本地引用")
                walk(item)
        elif isinstance(value, list):
            for item in value:
                walk(item)
    walk(schema)
    try:
        Draft202012Validator.check_schema(schema)
    except SchemaError:
        raise ValueError("工具 JSON Schema 无效") from None
    return Draft202012Validator(schema, registry=Registry())


class StdioTransport:
    def __init__(self, config):
        if not config.command or not Path(config.command[0]).is_absolute():
            raise ValueError("stdio command 必须指定受信绝对路径")
        env = {k: v for k, v in os.environ.items() if k.upper() in {"SYSTEMROOT", "WINDIR", "PATH", "TEMP", "TMP", "COMSPEC", "PATHEXT"}}
        env.update({k: resolve_secret(v) for k, v in config.env_refs.items()})
        self.process = subprocess.Popen(config.command, cwd=config.cwd, env=env, stdin=subprocess.PIPE,
            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0))
        self.queue = queue.Queue(maxsize=256)
        self.timeout = config.timeout
        def reader():
            try:
                while True:
                    line = self.process.stdout.readline(MAX_MESSAGE + 1)
                    if not line or len(line) > MAX_MESSAGE:
                        break
                    self.queue.put_nowait(json.loads(line))
            except (ValueError, OSError, queue.Full):
                pass
            finally:
                try:
                    self.queue.put_nowait(None)
                except queue.Full:
                    pass
        self.thread = threading.Thread(target=reader, daemon=True)
        self.thread.start()

    def exchange(self, message):
        self.process.stdin.write((json.dumps(message) + "\n").encode())
        self.process.stdin.flush()
        if "id" not in message or "method" not in message:
            return None
        deadline = time.monotonic() + self.timeout
        for _ in range(256):
            try:
                result = self.queue.get(timeout=max(.001, deadline - time.monotonic()))
            except queue.Empty:
                raise TimeoutError("MCP stdio 超时") from None
            if result is None:
                raise ValueError("MCP stdio 已关闭或输出无效")
            if "method" in result:
                if "id" in result:
                    self.exchange({"jsonrpc": "2.0", "id": result["id"], "error": {"code": -32601, "message": "Unsupported server request"}})
                continue
            if result.get("id") == message["id"]:
                return result
        raise ValueError("MCP 通知数量超过上限")

    def close(self):
        if self.process.poll() is None:
            self.process.terminate()
            try:
                self.process.wait(timeout=3)
            except subprocess.TimeoutExpired:
                self.process.kill()
                self.process.wait(timeout=3)
        for stream in (self.process.stdin, self.process.stdout):
            if stream:
                stream.close()
        self.thread.join(timeout=1)


class HTTPTransport:
    def __init__(self, config):
        parsed = urlparse(config.url or "")
        if (parsed.scheme != "https" and not (parsed.scheme == "http" and parsed.hostname in {"127.0.0.1", "::1", "localhost"})) or parsed.username or parsed.password or parsed.query or parsed.fragment:
            raise ValueError("MCP URL 必须为 HTTPS 或本机 HTTP，且不能内嵌凭据")
        self.config, self.session = config, None
        class NoRedirect(request.HTTPRedirectHandler):
            def redirect_request(self, *args, **kwargs):
                return None
        self.opener = request.build_opener(NoRedirect())

    def exchange(self, message):
        headers = {"Content-Type": "application/json", "Accept": "application/json, text/event-stream", "MCP-Protocol-Version": PROTOCOL}
        if self.session:
            headers["Mcp-Session-Id"] = self.session
        if self.config.auth_ref:
            headers["Authorization"] = "Bearer " + resolve_secret(self.config.auth_ref)
        req = request.Request(self.config.url, data=json.dumps(message).encode(), headers=headers, method="POST")
        with self.opener.open(req, timeout=self.config.timeout) as response:
            session = response.headers.get("Mcp-Session-Id")
            if session:
                if len(session) > 256 or not all(33 <= ord(c) <= 126 for c in session):
                    raise ValueError("无效 MCP session")
                self.session = session
            if "id" not in message:
                return None
            content_type = response.headers.get("Content-Type", "")
            if "text/event-stream" in content_type:
                total, parts = 0, []
                while total <= MAX_MESSAGE:
                    line = response.readline(MAX_MESSAGE + 1)
                    total += len(line)
                    if not line:
                        break
                    if line in {b"\n", b"\r\n"}:
                        if parts:
                            data = json.loads(b"\n".join(parts))
                            if data.get("id") == message["id"] and "method" not in data:
                                return data
                            parts = []
                    elif line.startswith(b"data:"):
                        parts.append(line[5:].strip())
                raise ValueError("MCP SSE 无有效响应或大小超限")
            raw = response.read(MAX_MESSAGE + 1)
            if len(raw) > MAX_MESSAGE:
                raise ValueError("MCP 响应过大")
            return json.loads(raw)

    def close(self):
        # 会话 DELETE 是可选功能；关闭本地引用，不重放工具请求。
        self.session = None


class MCPClient:
    def __init__(self, transport):
        self.transport, self.counter = transport, 0
        self.lock = threading.RLock()
        result = self.rpc("initialize", {"protocolVersion": PROTOCOL, "capabilities": {},
            "clientInfo": {"name": "agentloop", "version": "0.3.0"}})
        if result.get("protocolVersion") != PROTOCOL or "tools" not in result.get("capabilities", {}):
            transport.close()
            raise ValueError("MCP 协议版本或 tools 能力不兼容")
        self.transport.exchange({"jsonrpc": "2.0", "method": "notifications/initialized"})

    def rpc(self, method, params):
        with self.lock:
            self.counter += 1
            response = self.transport.exchange({"jsonrpc": "2.0", "id": self.counter, "method": method, "params": params})
            if not isinstance(response, dict) or response.get("jsonrpc") != "2.0" or response.get("id") != self.counter or "error" in response or "result" not in response:
                raise ValueError("MCP RPC 被拒绝或响应不匹配")
            return response["result"]

    def list_tools(self):
        tools, cursor, seen = [], None, set()
        for _ in range(20):
            result = self.rpc("tools/list", {"cursor": cursor} if cursor else {})
            tools.extend(result["tools"])
            cursor = result.get("nextCursor")
            if not cursor:
                break
            if cursor in seen:
                raise ValueError("MCP 分页 cursor 循环")
            seen.add(cursor)
        else:
            raise ValueError("MCP 工具分页超限")
        names = set()
        for tool in tools:
            if not re.fullmatch(r"[A-Za-z0-9_.-]{1,128}", tool["name"]) or tool["name"] in names:
                raise ValueError("MCP 工具名称无效或重复")
            validate_schema(tool["inputSchema"])
            names.add(tool["name"])
        return tools

    def close(self):
        self.transport.close()


class MCPRegistry:
    def __init__(self, repository, rbac, *, transport_factory=None):
        self.repo, self.store, self.rbac = repository, repository.store, rbac
        self.clients = {}
        self.transport_factory = transport_factory or (lambda c: StdioTransport(c) if c.transport == "stdio" else HTTPTransport(c))

    def register(self, run_id, config):
        if config.transport not in {"stdio", "http"}:
            raise ValueError("MCP transport 不支持")
        for policy in config.tools.values():
            if policy.capability not in CAPABILITY_REGISTRY:
                raise ValueError("MCP 使用未知能力")
        body = config.model_dump(mode="json")
        files = {}
        if config.transport == "stdio":
            for raw in [*config.command, *config.pinned_files]:
                path = Path(raw)
                if not path.is_absolute() and config.cwd:
                    path = Path(config.cwd) / path
                if path.is_file():
                    resolved = str(path.resolve())
                    with path.open("rb") as stream:
                        files[resolved] = hashlib.file_digest(stream, "sha256").hexdigest()
            if any(not Path(path).is_file() for path in config.pinned_files):
                raise ValueError("MCP 显式锁定的文件不存在")
        version = digest({"config": body, "files": files})
        project = self.store.get_run(run_id).project_id
        with self.store.transaction():
            if not self.store.runtime_get("mcp_version", version):
                self.store.runtime_put("mcp_version", version, {"hash": version, "config": body, "files": files, "project": project,
                    "run_id": run_id, "status": "QUARANTINED"})
                self.repo.audit(run_id, "MCP_QUARANTINED", {"server_id": config.server_id, "hash": version})
        return version

    def approve(self, version, principal_id):
        record = self.store.runtime_get("mcp_version", version)
        self.rbac.require_human(principal_id)
        self.rbac.require_role(principal_id, "project_owner", record["project"])
        record.update(status="APPROVED", principal_id=principal_id)
        with self.store.transaction():
            self.store.runtime_put("mcp_version", version, record)
            self.store.runtime_put("mcp_current", f"{record['project']}/{record['config']['server_id']}", {"hash": version})
            self.repo.audit(record["run_id"], "MCP_APPROVED", {"hash": version, "principal_id": principal_id})

    def start(self, version):
        record = self.store.runtime_get("mcp_version", version)
        if not record or record["status"] != "APPROVED":
            raise PermissionError("隔离 MCP 未经人工批准，禁止启动")
        if version in self.clients:
            return self.clients[version]
        for filename, expected in record.get("files", {}).items():
            path = Path(filename)
            if not path.is_file():
                raise ValueError("MCP 锁定启动文件缺失")
            with path.open("rb") as stream:
                if hashlib.file_digest(stream, "sha256").hexdigest() != expected:
                    raise ValueError("MCP 启动文件改变，必须作为新版本重新登记审批")
        config = ServerConfig.model_validate(record["config"])
        transport = self.transport_factory(config)
        try:
            client = MCPClient(transport)
            tools = client.list_tools()
            # 服务器自己声明的 annotations 不能赋予 read-only 或生产能力。
            available = {tool["name"]: tool for tool in tools if tool["name"] in config.tools}
            if set(available) != set(config.tools):
                raise ValueError("授权清单存在服务端未提供的工具")
            old = self.store.runtime_get("mcp_schema", version)
            if old and digest(old) != digest(available):
                raise ValueError("同一 MCP 版本工具 Schema 漂移，必须重新登记审批")
            self.store.runtime_put("mcp_schema", version, available)
            self.clients[version] = client
            self.repo.audit(record["run_id"], "MCP_STARTED", {"hash": version, "tools": list(available)})
            return client
        except BaseException:
            transport.close()
            raise

    def stop(self, version):
        client = self.clients.pop(version, None)
        if client:
            client.close()

    def disable(self, version, principal_id, *, uninstall=False):
        record = self.store.runtime_get("mcp_version", version)
        self.rbac.require_human(principal_id)
        self.rbac.require_role(principal_id, "project_owner", record["project"])
        self.stop(version)
        record["status"] = "UNINSTALLED" if uninstall else "DISABLED"
        self.store.runtime_put("mcp_version", version, record)
        self.repo.audit(record["run_id"], "MCP_" + record["status"], {"hash": version})

    def approve_call(self, request_id, principal_id):
        with self.store.transaction():
            approval = self.store.runtime_get("tool_approval", request_id)
            if not approval or approval["status"] != "PENDING" or approval["expires_at"] <= utc_now().isoformat():
                raise ValueError("工具调用审批不存在、已处理或已过期")
            run = self.store.get_run(approval["run_id"])
            self.rbac.require_human(principal_id)
            self.rbac.require_role(principal_id, "project_owner", run.project_id)
            config = self.repo.load_snapshot(run.run_id, approval["role"])
            if approval["config_digest"] != digest(config.model_dump(mode="json")):
                raise ValueError("工具调用审批配置已变化")
            approval.update(status="APPROVED", principal_id=principal_id)
            self.store.runtime_put("tool_approval", request_id, approval)
            self.repo.audit(run.run_id, "TOOL_CALL_APPROVED", {k: v for k, v in approval.items()})

    def visible(self, config):
        result = []
        for identifier in config.policy.tools:
            if identifier in config.policy.denied_tools or "/" not in identifier:
                continue
            server, name = identifier.split("/", 1)
            result.append({"server_id": server, "tool_name": name})
        return result

    def describe(self, run_id, config):
        project = self.store.get_run(run_id).project_id
        result = []
        for tool in self.visible(config):
            server_id, name = tool["server_id"], tool["tool_name"]
            pin_key = f"{run_id}/{config.role}/{server_id}"
            with self.store.transaction():
                pin = self.store.runtime_get("mcp_pin", pin_key) or self.store.runtime_get("mcp_current", f"{project}/{server_id}")
                if not pin:
                    raise PermissionError("配置中的 MCP 尚未人工批准")
                record = self.store.runtime_get("mcp_version", pin["hash"])
                server = ServerConfig.model_validate(record["config"])
                tool_policy = server.tools.get(name)
                if tool_policy is None:
                    raise ValueError("配置工具在受信 MCP 注册清单中不存在")
                if (tool_policy.capability not in config.policy.capabilities
                        or tool_policy.capability in INDEPENDENT_EXECUTOR_CAPABILITIES):
                    continue
                refs = set(server.env_refs.values()) | ({server.auth_ref} if server.auth_ref else set())
                if not refs <= set(config.policy.secrets) or (server.transport == "http" and urlparse(server.url).hostname not in config.policy.network_hosts):
                    raise PermissionError("MCP 连接超出角色秘密/网络授权")
                if record["project"] != project or record["status"] != "APPROVED":
                    raise PermissionError("MCP 版本无效")
                self.store.runtime_put("mcp_pin", pin_key, pin)
            self.start(pin["hash"])
            schema = self.store.runtime_get("mcp_schema", pin["hash"]).get(name)
            if not schema:
                raise ValueError("配置工具在 MCP 中不存在")
            # 服务端描述是不可信数据，仅放在 user 区域。
            result.append({**tool, "server_hash": pin["hash"], "inputSchema": schema["inputSchema"],
                           "untrusted_description": schema.get("description", "")})
        return result

    def call(self, *, run_id, config, server_id, tool_name, arguments, idempotency_key):
        try:
            return self._call(run_id=run_id, config=config, server_id=server_id, tool_name=tool_name,
                              arguments=arguments, idempotency_key=idempotency_key)
        except PermissionError as exc:
            # 在被拒业务事务回滚以后记录，拒绝证据不能随事务一起丢失。
            self.repo.audit(run_id, "TOOL_ACCESS_DENIED", {"role": config.role, "tool": f"{server_id}/{tool_name}",
                "policy_id": config.policy.policy_id, "reason": str(exc)})
            raise

    def _call(self, *, run_id, config, server_id, tool_name, arguments, idempotency_key):
        if not isinstance(idempotency_key, str) or not idempotency_key or len(idempotency_key) > 200:
            raise ValueError("MCP 幂等键不能为空或超长")
        identifier = f"{server_id}/{tool_name}"
        project = self.store.get_run(run_id).project_id
        def deny(reason):
            raise PermissionError(reason)
        # 从持久不可变快照读取权限，拒绝以另一个 config 扩权。
        saved = self.repo.load_snapshot(run_id, config.role)
        if saved != config:
            deny("有效配置不匹配")
        if identifier not in config.policy.tools or identifier in config.policy.denied_tools:
            deny("四级工具授权交集拒绝")
        with self.store.transaction():
            pin_key = f"{run_id}/{config.role}/{server_id}"
            pin = self.store.runtime_get("mcp_pin", pin_key)
            current = pin or self.store.runtime_get("mcp_current", f"{project}/{server_id}")
            if not current:
                deny("MCP 尚未批准")
            version = current["hash"]
            record = self.store.runtime_get("mcp_version", version)
            if record["status"] != "APPROVED" or record["project"] != project:
                deny("MCP 版本已停用或跨项目")
            server = ServerConfig.model_validate(record["config"])
            policy = server.tools.get(tool_name)
            if not policy or policy.capability not in config.policy.capabilities:
                deny("能力上限拒绝")
            if policy.capability in INDEPENDENT_EXECUTOR_CAPABILITIES:
                deny("此能力必须使用独立审批执行器，Phase 2 MCP 禁止执行")
            refs = set(server.env_refs.values()) | ({server.auth_ref} if server.auth_ref else set())
            if not refs <= set(config.policy.secrets):
                deny("服务凭据引用超出角色授权")
            if server.transport == "http" and urlparse(server.url).hostname not in config.policy.network_hosts:
                deny("MCP 网络出口拒绝")
            for name in policy.path_parameters:
                value = arguments.get(name)
                if not isinstance(value, str) or not Path(value).is_absolute() or not any(Path(value).resolve().is_relative_to(Path(root).resolve()) for root in config.policy.workspace_roots):
                    deny("工具目录访问拒绝")
            for name in policy.url_parameters:
                parsed = urlparse(arguments.get(name, ""))
                if parsed.scheme != "https" or parsed.hostname not in config.policy.network_hosts or parsed.username or parsed.password:
                    deny("工具网络出口拒绝")
            self.store.runtime_put("mcp_pin", pin_key, {"hash": version})
        params_hash = digest(arguments)
        call_key = digest({"run": run_id, "role": config.role, "key": idempotency_key})
        existing = self.store.runtime_get("mcp_call", call_key)
        if existing:
            if (existing["params_hash"], existing["server_hash"], existing["tool"]) != (params_hash, version, identifier):
                raise ValueError("MCP 幂等键已绑定其他请求")
            if existing["status"] == "SUCCEEDED":
                return existing["result"]
            raise ValueError("MCP 调用状态不明或失败，禁止自动重放")
        approval_id = None
        if policy.mutating and config.policy.requires_human_approval:
            approval_id = digest({"call": call_key, "params": params_hash, "version": version, "tool": identifier})
            with self.store.transaction():
                approval = self.store.runtime_get("tool_approval", approval_id)
                if approval is None:
                    approval = {"id": approval_id, "run_id": run_id, "role": config.role, "tool": identifier,
                        "params_hash": params_hash, "server_hash": version, "config_digest": digest(config.model_dump(mode="json")),
                        "review_arguments": sanitized_review(arguments, [resolve_secret(ref) for ref in refs]),
                        "expires_at": (utc_now() + timedelta(minutes=30)).isoformat(), "status": "PENDING"}
                    self.store.runtime_put("tool_approval", approval_id, approval)
                    self.repo.audit(run_id, "TOOL_CALL_APPROVAL_REQUESTED", approval)
            if approval["status"] != "APPROVED" or approval["expires_at"] <= utc_now().isoformat():
                deny("写入工具需人工批准，request_id=" + approval_id)
        client = self.start(version)
        schema = self.store.runtime_get("mcp_schema", version)[tool_name]["inputSchema"]
        if not validate_schema(schema).is_valid(arguments):
            raise ValueError("MCP 参数不符合已固定 Schema")
        with self.store.transaction():
            existing = self.store.runtime_get("mcp_call", call_key)
            if existing:
                if (existing["params_hash"], existing["server_hash"], existing["tool"]) != (params_hash, version, identifier):
                    raise ValueError("MCP 幂等键已绑定其他请求")
                if existing["status"] == "SUCCEEDED":
                    return existing["result"]
                raise ValueError("MCP 调用状态不明或失败，禁止自动重放")
            receipt = {"id": call_key, "run_id": run_id, "role": config.role, "tool": identifier,
                "server_hash": version, "params_hash": params_hash, "status": "STARTED", "mutating": policy.mutating}
            if approval_id:
                current = self.store.runtime_get("tool_approval", approval_id)
                if current["status"] != "APPROVED" or current["expires_at"] <= utc_now().isoformat():
                    deny("工具批准已失效或使用")
                current["status"] = "CONSUMED"
                self.store.runtime_put("tool_approval", approval_id, current)
            self.store.runtime_put("mcp_call", call_key, receipt)
        start = time.monotonic()
        try:
            result = client.rpc("tools/call", {"name": tool_name, "arguments": arguments})
            secrets = [resolve_secret(ref) for ref in refs]
            def redact(value):
                if isinstance(value, str):
                    for secret in secrets:
                        value = value.replace(secret, "[REDACTED]")
                    return value
                if isinstance(value, dict):
                    return {redact(k): redact(v) for k, v in value.items()}
                if isinstance(value, list):
                    return [redact(v) for v in value]
                return value
            result = redact(result)
            safe = json.dumps(result, ensure_ascii=False)
            receipt.update(result=result, status="FAILED" if result.get("isError") else "SUCCEEDED")
            if any(x in safe.lower() for x in ("skip g2", "ignore previous", "泄露密钥", "approve memory")):
                self.repo.audit(run_id, "UNTRUSTED_INSTRUCTION_DETECTED", {"role": config.role, "source": identifier, "content_hash": digest(safe)})
        except BaseException:
            receipt["status"] = "UNKNOWN"
            raise ValueError("MCP 调用中断，需核对后再处理，原请求不会自动重放") from None
        finally:
            receipt["duration_ms"] = round((time.monotonic() - start) * 1000)
            with self.store.transaction():
                self.store.runtime_put("mcp_call", call_key, receipt)
                self.repo.audit(run_id, "MCP_CALL", {k: v for k, v in receipt.items() if k != "result"})
        if receipt["status"] != "SUCCEEDED":
            raise ValueError("MCP 返回工具错误")
        return receipt["result"]

    def close(self):
        for version in list(self.clients):
            self.stop(version)
