"""四级配置、不可变快照与秘密引用。权限不接受自然语言覆盖。"""

import hashlib
import os
import re
from pathlib import Path
from ...knowledge.archive import canonical
from ..contracts.phase2 import EffectiveConfig, Policy


def digest(value):
    return hashlib.sha256(canonical(value).encode()).hexdigest()


def resolve_secret(ref):
    if not re.fullmatch(r"env:[A-Z][A-Z0-9_]{0,100}", ref):
        raise ValueError("只允许 env:NAME 形式的秘密引用")
    value = os.environ.get(ref[4:])
    if not value:
        raise ValueError("秘密引用不可解析")
    return value


def effective_config(config, role):
    entry = config.roles[role]
    layers = [config.platform, config.departments[entry.department], entry.agent, entry.task]
    if layers[0].policy is None:
        raise ValueError("平台必须显式声明权限上限")
    policies = [layer.policy for layer in layers if layer.policy is not None]
    fields = ("models", "tools", "capabilities", "network_hosts", "secrets")
    merged = {name: sorted(set.intersection(*(set(getattr(p, name)) for p in policies))) for name in fields}
    roots = [Path(p).resolve() for p in policies[0].workspace_roots]
    for policy in policies[1:]:
        roots = [child for child in map(lambda p: Path(p).resolve(), policy.workspace_roots)
                 if any(child.is_relative_to(parent) for parent in roots)]
    merged["workspace_roots"] = sorted(set(map(str, roots)))
    merged["denied_tools"] = sorted({tool for p in policies for tool in p.denied_tools})
    merged["tools"] = sorted(set(merged["tools"]) - set(merged["denied_tools"]))
    merged["requires_human_approval"] = any(p.requires_human_approval for p in policies)
    merged["policy_id"] = digest([p.model_dump(mode="json") for p in policies])
    values = {"fallbacks": [], "max_steps": 100, "concurrency": 1, "skills": {}, "prompt_version": "v1"}
    for layer in layers:
        values.update({k: v for k, v in layer.model_dump(mode="json", exclude_none=True).items() if k != "policy"})
    # 降低预算可以，子层不能扩大父层预算/步骤/并发上限。
    for name in ("token_budget", "cost_budget", "max_steps", "concurrency"):
        ceilings = [getattr(layer, name) for layer in layers if getattr(layer, name) is not None]
        if ceilings:
            values[name] = min(ceilings)
    chain = [values.get("primary"), *values["fallbacks"]]
    return EffectiveConfig(role=role, department=entry.department, policy=Policy(**merged),
        models={k: v for k, v in config.models.items() if k in chain}, **values)


class RuntimeRepository:
    def __init__(self, store, archive):
        self.store, self.archive = store, archive

    def audit(self, run_id, action, body):
        from ..contracts.enums import ActorType, EventType, TrustLevel
        from uuid import uuid4
        artifact = self.archive.put(run_id=run_id, kind="RUNTIME_AUDIT", producer="runtime-policy",
            value={"action": action, **body}, trust=TrustLevel.VERIFIED_INTERNAL)
        event_type = {"UNTRUSTED_INSTRUCTION_DETECTED": EventType.UNTRUSTED_INSTRUCTION_DETECTED,
                      "TOOL_ACCESS_DENIED": EventType.ACCESS_DENIED}.get(action, EventType.RUNTIME_AUDIT)
        self.store.append_event(run_id=run_id, event_type=event_type,
            actor_id="runtime-policy", actor_type=ActorType.SYSTEM, payload_ref=artifact.artifact_id,
            idempotency_key=f"{run_id}:runtime:{uuid4().hex}")
        return artifact

    def snapshot(self, run_id, config):
        body = config.model_dump(mode="json")
        key = f"{run_id}/{config.role}"
        with self.store.transaction():
            existing = self.store.runtime_get("config", key)
            if existing is not None:
                if existing["digest"] != digest(body):
                    raise ValueError("运行中的有效配置不可变；变更必须创建新 Run")
                return existing
            artifact = self.archive.put(run_id=run_id, kind="EFFECTIVE_CONFIG", producer="runtime-policy", value=body)
            record = {"run_id": run_id, "role": config.role, "digest": digest(body), "artifact_id": artifact.artifact_id}
            self.store.runtime_put("config", key, record)
            return record

    def load_snapshot(self, run_id, role):
        saved = self.store.runtime_get("config", f"{run_id}/{role}")
        if not saved:
            raise ValueError("有效配置快照不存在")
        body = self.archive.read(saved["artifact_id"], run_id=run_id)
        if digest(body) != saved["digest"]:
            raise ValueError("有效配置哈希校验失败")
        return EffectiveConfig.model_validate(body)
