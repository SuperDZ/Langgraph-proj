"""Phase 2 配置契约。金额统一使用整数 micro-USD，不使用浮点累计。"""

from typing import Any, Literal
from pydantic import Field, model_validator
from .models import StrictModel


class RuntimeRecord(StrictModel):
    data: dict[str, Any]


class ModelProfile(StrictModel):
    provider: Literal["deepseek", "fixture"] = "deepseek"
    model: str = Field(min_length=1)
    secret_ref: str = Field(default="env:DEEPSEEK_API_KEY", pattern=r"^env:[A-Z][A-Z0-9_]{0,100}$")
    endpoint: str = "https://api.deepseek.com"
    temperature: float | None = Field(default=0, ge=0, le=2)
    max_output_tokens: int = Field(default=2048, ge=1, le=32768)
    timeout_seconds: float = Field(default=60, gt=0, le=300)
    retries: int = Field(default=2, ge=0, le=5)
    thinking: Literal["enabled", "disabled"] = "disabled"
    reasoning_effort: Literal["none", "low", "high", "max"] | None = None
    structured_output: bool = True
    tool_calling: bool = False
    residency: str = "configured-provider"
    audit: bool = True
    # micro-USD/token，必须由受信配置明确给出；不是实际账单。
    input_rate: int = Field(default=1, ge=0)
    output_rate: int = Field(default=2, ge=0)

    @model_validator(mode="after")
    def supported_parameters(self):
        from urllib.parse import urlparse
        endpoint = urlparse(self.endpoint)
        if endpoint.scheme != "https" or not endpoint.hostname or endpoint.username or endpoint.password or endpoint.query or endpoint.fragment:
            raise ValueError("模型端点必须为不含凭据的 HTTPS URL")
        thinking = self.thinking == "enabled" or self.reasoning_effort in {"low", "high", "max"}
        if thinking and self.temperature is not None:
            raise ValueError("thinking 模式不支持 temperature，请显式配置为 null")
        if self.thinking == "enabled" and self.reasoning_effort == "none":
            raise ValueError("thinking 与 reasoning_effort 互相冲突")
        return self


class Policy(StrictModel):
    policy_id: str
    models: list[str] = Field(default_factory=list)
    tools: list[str] = Field(default_factory=list)
    denied_tools: list[str] = Field(default_factory=list)
    capabilities: list[str] = Field(default_factory=list)
    workspace_roots: list[str] = Field(default_factory=list)
    network_hosts: list[str] = Field(default_factory=list)
    secrets: list[str] = Field(default_factory=list)
    requires_human_approval: bool = True


class ConfigLayer(StrictModel):
    policy: Policy | None = None
    primary: str | None = None
    fallbacks: list[str] | None = None
    token_budget: int | None = Field(default=None, gt=0)
    cost_budget: int | None = Field(default=None, gt=0)
    max_steps: int | None = Field(default=None, gt=0, le=500)
    concurrency: int | None = Field(default=None, ge=1, le=32)
    prompt_version: str | None = None
    skills: dict[str, str] | None = None


class EffectiveConfig(StrictModel):
    role: str
    department: str
    primary: str
    fallbacks: list[str]
    token_budget: int = Field(gt=0)
    cost_budget: int = Field(gt=0)
    max_steps: int = Field(gt=0)
    concurrency: int = Field(gt=0)
    prompt_version: str
    skills: dict[str, str]
    policy: Policy
    models: dict[str, ModelProfile]

    @model_validator(mode="after")
    def chain_valid(self):
        chain = [self.primary, *self.fallbacks]
        if len(chain) != len(set(chain)) or not set(chain) <= set(self.policy.models):
            raise ValueError("后备链重复或越过模型授权")
        if any(name not in self.models for name in chain):
            raise ValueError("模型配置不存在")
        baseline = self.models[self.primary]
        for name in chain:
            model = self.models[name]
            if not model.structured_output or not model.audit or model.residency != baseline.residency:
                raise ValueError("后备模型不兼容结构化输出、驻留或审计策略")
            if baseline.tool_calling and not model.tool_calling:
                raise ValueError("后备模型缺少工具调用能力")
            if model.secret_ref not in self.policy.secrets:
                raise ValueError("模型凭据引用未授权")
            from urllib.parse import urlparse
            if urlparse(model.endpoint).hostname not in self.policy.network_hosts:
                raise ValueError("模型端点不在网络出口授权内")
        return self


class RoleConfig(StrictModel):
    department: str
    agent: ConfigLayer = Field(default_factory=ConfigLayer)
    task: ConfigLayer = Field(default_factory=ConfigLayer)


class RuntimeConfig(StrictModel):
    models: dict[str, ModelProfile]
    platform: ConfigLayer
    departments: dict[str, ConfigLayer]
    roles: dict[str, RoleConfig]
    run_token_budget: int = Field(gt=0)
    run_cost_budget: int = Field(gt=0)
