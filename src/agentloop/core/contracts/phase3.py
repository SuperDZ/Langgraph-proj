"""发布执行、运维和隔离研发的服务端契约。"""

from typing import Literal
from pathlib import PurePosixPath
from urllib.parse import urlparse
from pydantic import Field, model_validator
from .models import StrictModel


class DeploymentTarget(StrictModel):
    target_id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,80}$")
    project_id: str
    environment: Literal["staging", "production"]
    provider: Literal["local-static", "http-agent"]
    endpoint: str | None = None
    secret_ref: str | None = Field(default=None, pattern=r"^env:[A-Z][A-Z0-9_]*$")
    health_path: str = "/index.html"
    expected_text: str = Field(default="AgentLoop", min_length=1, max_length=1000)
    timeout_seconds: float = Field(default=10, gt=0, le=60)

    @model_validator(mode="after")
    def safe_endpoint(self):
        path = PurePosixPath(self.health_path)
        if not self.health_path.startswith("/") or ".." in path.parts or "\\" in self.health_path or "?" in self.health_path:
            raise ValueError("健康检查路径不安全")
        if self.provider == "local-static" and self.environment != "staging":
            raise ValueError("本地静态目标仅用于 staging")
        if self.provider == "http-agent":
            parsed = urlparse(self.endpoint or "")
            local = parsed.hostname in {"localhost", "127.0.0.1", "::1"}
            if (parsed.scheme != "https" and not (parsed.scheme == "http" and local and self.environment == "staging")) or parsed.username or parsed.password or parsed.query or parsed.fragment:
                raise ValueError("远端执行代理须使用无内嵌凭据的 HTTPS；本地 staging 可用 HTTP")
            if not self.secret_ref:
                raise ValueError("执行代理必须声明认证秘密引用")
        return self


class ExecutionPolicy(StrictModel):
    principal_id: str
    role: Literal["operations-expert", "backend", "frontend", "devops"]
    platform: list[str]
    department: list[str]
    agent: list[str]
    task: list[str]
    denied: list[str] = Field(default_factory=list)
    target_ids: list[str]
    network_hosts: list[str] = Field(default_factory=list)
    secrets: list[str] = Field(default_factory=list)

    def grants(self):
        values = set(self.platform) & set(self.department) & set(self.agent) & set(self.task) - set(self.denied)
        if self.role != "operations-expert":
            values -= {"cap.deploy.production", "cap.deploy.staging"}
        return values


class DeploymentObservation(StrictModel):
    operation_id: str
    status: Literal["SUCCEEDED", "FAILED", "UNKNOWN", "NOT_FOUND", "CANCELLED"]
    artifact_digest: str | None = None
    previous_digest: str | None = None
    healthy: bool = False
    evidence: str = ""


class WorkerTask(StrictModel):
    task_id: str = Field(pattern=r"^[A-Za-z0-9_-]{1,80}$")
    role: Literal["backend", "frontend", "devops"]
    editable_paths: list[str] = Field(min_length=1)


class StaticServiceConfig(StrictModel):
    service: str = "agentloop-demo"
    kind: Literal["static"] = "static"
    document: Literal["web/index.html"] = "web/index.html"
    health_path: Literal["/index.html"] = "/index.html"
