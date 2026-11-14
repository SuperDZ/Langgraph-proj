"""RBAC 与 Capability 交集。

规范约束（§2.8 / REQ-015、REQ-043、附录 A）：
- 主体分为 human_user / agent_service / system_service
- RBAC 由后端认证令牌的可信身份映射；Agent 文字输出不能赋予自己权限
- 系统 Agent 作为 agent_service 不能获得发布批准人权限
- 有效授权 = 上级授权范围与本级申请权限的交集；显式 deny 永远优先
- 不可通过配置覆盖提升的权限：MCP Tool、目录访问、密钥、网络出口、生产部署

三套命名严格分离：
- Role（谁能批准/发起/执行）—— 不当作 MCP 工具 grant
- Capability（cap.*，Agent/服务可调用的能力上限）
- ReleaseAction（DEPLOY/ROLLBACK，发布授权允许的操作）
"""

from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from ..contracts.enums import PrincipalType
from ..contracts.models import CapabilitySet, Principal, RoleBinding, utc_now


class Capability(str):
    """cap.* 能力标识。使用规范 §2.8 词表。"""

    REPO_READ = "cap.repo.read"
    WORKSPACE_WRITE = "cap.workspace.write"
    TESTS_EXECUTE = "cap.tests.execute"
    SANDBOX_EXECUTE = "cap.sandbox.execute"
    EXTERNAL_WRITE = "cap.external.write"
    DEPLOY_STAGING = "cap.deploy.staging"
    DEPLOY_PRODUCTION = "cap.deploy.production"
    SECRETS_MANAGE = "cap.secrets.manage"
    MEMORY_REVIEW = "cap.memory.review"
    RISK_WAIVER_APPROVE = "cap.risk_waiver.approve"


CAPABILITY_REGISTRY: frozenset[str] = frozenset(
    {
        Capability.REPO_READ,
        Capability.WORKSPACE_WRITE,
        Capability.TESTS_EXECUTE,
        Capability.SANDBOX_EXECUTE,
        Capability.EXTERNAL_WRITE,
        Capability.DEPLOY_STAGING,
        Capability.DEPLOY_PRODUCTION,
        Capability.SECRETS_MANAGE,
        Capability.MEMORY_REVIEW,
        Capability.RISK_WAIVER_APPROVE,
    }
)

#: 旧字段或值的迁移映射（附录 A）。仅用于解析旧配置；新文件必须使用规范标识。
LEGACY_CAPABILITY_MAP: dict[str, str] = {
    "read_repo": Capability.REPO_READ,
    "read": Capability.REPO_READ,  # 含糊 read 需单独校验，见resolve_capability
    "write_worktree": Capability.WORKSPACE_WRITE,
    "write_workspace": Capability.WORKSPACE_WRITE,
    "run_tests": Capability.TESTS_EXECUTE,
    "run_sandbox": Capability.SANDBOX_EXECUTE,
    "external_write": Capability.EXTERNAL_WRITE,
    "deploy_staging": Capability.DEPLOY_STAGING,
    "production_deploy": Capability.DEPLOY_PRODUCTION,
    "production-deploy": Capability.DEPLOY_PRODUCTION,
    "deploy_production": Capability.DEPLOY_PRODUCTION,
    "manage_secrets": Capability.SECRETS_MANAGE,
}


class ConfigError(Exception):
    """配置错误。含混权限必须报错，不能默认提升。"""


def resolve_capability(raw: str, *, resource_hint: str | None = None) -> str:
    """把旧配置值解析为规范 cap.* 标识。"""
    if raw in CAPABILITY_REGISTRY:
        return raw
    if raw == "read" and resource_hint == "repo":
        return Capability.REPO_READ
    if raw == "read":
        # 旧配置若单独出现含混 read 且无法确定资源类型，必须报配置错误
        raise ConfigError(
            f"含混权限 'read' 无法确定资源类型，必须显式写为 {Capability.REPO_READ}；"
            "不能默认提升为广泛资源读取权限"
        )
    if raw in LEGACY_CAPABILITY_MAP:
        return LEGACY_CAPABILITY_MAP[raw]
    raise ConfigError(f"未知的权限标识 '{raw}'，请使用规范 cap.* 名称")


#: 建议角色（规范 §2.8）。角色可组合，服务端实施最小权限。
ROLE_DEFINITIONS: dict[str, set[str]] = {
    "side_effect_executor": {"cap.deploy.staging", "cap.deploy.production"},
    "platform_admin": {
        "cap.repo.read",
        "cap.workspace.write",
        "cap.memory.review",
    },
    "project_owner": {"cap.repo.read", "cap.risk_waiver.approve"},
    "product_approver": {"cap.repo.read"},
    "release_approver": {"cap.repo.read"},  # 批准权，不含部署执行
    "security_reviewer": {
        "cap.repo.read",
        "cap.risk_waiver.approve",
        "cap.memory.review",
    },
    "memory_reviewer": {
        "cap.repo.read",
        "cap.memory.review",
    },
    "operator": {"cap.repo.read", "cap.deploy.staging"},
    "viewer": {"cap.repo.read"},
}

#: agent_service 绝不允许获得的角色。
AGENT_FORBIDDEN_ROLES: frozenset[str] = frozenset({"release_approver", "side_effect_executor"})


class AccessDenied(Exception):
    """权限不足。对应 API 层 403 FORBIDDEN。"""

    def __init__(self, principal_id: str, reason: str) -> None:
        super().__init__(reason)
        self.principal_id = principal_id
        self.reason = reason


class RBACService:
    """角色绑定与能力求交。"""

    def __init__(self, store=None) -> None:
        from ..orchestration.store import InMemoryStore
        self.store = store or InMemoryStore()

    # ------------------------------------------------------------------

    def register_principal(
        self,
        principal_id: str,
        principal_type: PrincipalType,
        identity_provider_ref: str,
    ) -> Principal:
        principal = Principal(
            principal_id=principal_id,
            principal_type=principal_type,
            identity_provider_ref=identity_provider_ref,
        )
        try:
            existing = self.store.get_principal(principal_id)
        except KeyError:
            existing = None
        if existing is not None and existing != principal:
            raise AccessDenied(principal_id, "已注册主体的身份不可覆盖")
        self.store.put_principal(principal)
        return principal

    def get_principal(self, principal_id: str) -> Principal:
        try:
            principal = self.store.get_principal(principal_id)
        except KeyError as exc:
            raise AccessDenied(principal_id, "主体未注册或身份不可信") from exc
        if principal.status != "ACTIVE":
            raise AccessDenied(principal_id, "主体已停用")
        return principal

    def bind_role(
        self,
        *,
        principal_id: str,
        role_id: str,
        scope_type: str,
        scope_id: str,
        valid_from: datetime,
        valid_until: datetime | None = None,
        actor_id: str = "platform_admin",
    ) -> RoleBinding:
        """由有权管理员分配角色。拒绝给 Agent 服务身份发布批准人权限。"""
        principal = self.get_principal(principal_id)
        if ((role_id == "side_effect_executor" and principal.principal_type is not PrincipalType.SYSTEM_SERVICE)
                or (role_id != "side_effect_executor" and principal.principal_type is not PrincipalType.HUMAN_USER and role_id in AGENT_FORBIDDEN_ROLES)):
            raise AccessDenied(
                principal_id,
                f"agent_service 不得获得角色 {role_id}；发布批准必须由真人签发",
            )
        if role_id not in ROLE_DEFINITIONS:
            raise ConfigError(f"未知角色 {role_id}")

        if scope_type not in {"project", "platform"} or (scope_type == "platform" and scope_id != "*"):
            raise ConfigError("非法角色作用域")
        if valid_until is not None and valid_until <= valid_from:
            raise ConfigError("角色有效期为空")
        binding = RoleBinding(
            binding_id=f"rb-{uuid4().hex}",
            principal_id=principal_id,
            role_id=role_id,
            scope_type=scope_type,
            scope_id=scope_id,
            valid_from=valid_from,
            valid_until=valid_until,
        )
        self.store.put_role_binding(binding)
        return binding

    def roles_of(
        self, principal_id: str, scope_id: str, moment: datetime | None = None
    ) -> set[str]:
        moment = moment or utc_now()
        self.get_principal(principal_id)
        return {
            b.role_id
            for b in self.store.role_bindings()
            if b.principal_id == principal_id
            and b.scope_id == scope_id
            and b.is_effective_at(moment)
        }

    def has_role(self, principal_id: str, role_id: str, scope_id: str) -> bool:
        return role_id in self.roles_of(principal_id, scope_id)

    def require_role(self, principal_id: str, role_id: str, scope_id: str) -> None:
        if not self.has_role(principal_id, role_id, scope_id):
            raise AccessDenied(
                principal_id, f"缺少角色 {role_id}（scope={scope_id}）"
            )

    def require_human(self, principal_id: str) -> Principal:
        """要求真人主体。Agent 服务身份不能代替真人决策。"""
        principal = self.get_principal(principal_id)
        if principal.principal_type is not PrincipalType.HUMAN_USER:
            raise AccessDenied(principal_id, "该操作要求 human_user 主体")
        return principal

    def project_of(self, principal_id: str) -> str | None:
        for b in self.store.role_bindings():
            if b.principal_id == principal_id and b.scope_type == "project":
                return b.scope_id
        return None

    def assert_project_access(self, principal_id: str, project_id: str, moment=None) -> None:
        """项目隔离：不能借 Run ID 绕过项目边界（AC-48）。"""
        roles = self.roles_of(principal_id, project_id, moment)
        if roles:
            return
        if "platform_admin" in self.roles_of(principal_id, "*", moment):
            return
        raise AccessDenied(
            principal_id, f"无权访问项目 {project_id}；不能借 Run ID 绕过项目隔离"
        )


# --------------------------------------------------------------------------
# Capability 求交
# --------------------------------------------------------------------------


class CapabilityResolver:
    """平台 ∩ 部门 ∩ Agent ∩ 任务的有效能力计算。

    不可通过覆盖提升的权限走交集（永远不扩张）；
    显式 deny 永远优先（规范 §3.2）。
    """

    def __init__(
        self,
        *,
        platform_default: CapabilitySet,
        department_max: CapabilitySet,
        department_deny: frozenset[str] = frozenset(),
    ) -> None:
        self.platform_default = platform_default
        self.department_max = department_max
        self.department_deny = department_deny

    def effective_for_agent(
        self,
        *,
        agent_requested: CapabilitySet,
        agent_deny: frozenset[str] = frozenset(),
    ) -> CapabilitySet:
        effective = self.platform_default.intersect(self.department_max)
        effective = effective.intersect(agent_requested)
        effective = effective.denied_by(self.department_deny).denied_by(agent_deny)
        return effective

    def effective_for_task(
        self,
        agent_effective: CapabilitySet,
        *,
        task_grants: CapabilitySet | None = None,
        task_deny: frozenset[str] = frozenset(),
    ) -> CapabilitySet:
        """任务覆盖只允许缩小权限，不能提升。"""
        effective = agent_effective
        if task_grants is not None:
            effective = effective.intersect(task_grants)
        return effective.denied_by(task_deny)


def assert_capability(
    effective: CapabilitySet, required: str, *, principal_id: str = "unknown"
) -> None:
    """最终允许执行判定的一环。"""
    if required not in effective.grants:
        raise AccessDenied(
            principal_id,
            f"缺少能力 {required}；有效授权为 {sorted(effective.grants)}",
        )
