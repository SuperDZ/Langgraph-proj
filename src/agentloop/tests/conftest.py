"""Phase 0 验收测试的共享夹具与假环境。

规范 §12.1 要求注入的假环境：
假模型、假 MCP、假部署服务器、假身份、假时钟、可冲突的 Git 仓库。

Phase 0 只需要其中与确定性骨架相关的部分：假身份、假时钟、
以及一套可注入的 Mock Agent（Phase 0 不调用真实模型）。
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest

from agentloop.core.approvals import (
    ApprovalRequestService,
    Capability,
    CapabilityResolver,
    RBACService,
)
from agentloop.core.contracts.enums import (
    GateId,
    PrincipalType,
    RunPhase,
    RunStatus,
    RunType,
)
from agentloop.core.contracts.models import CapabilitySet, utc_now
from agentloop.core.orchestration import (
    GateEvaluator,
    InMemoryStore,
    StateTransitionService,
)
from agentloop.core.routing import LoopRouter

T0 = datetime(2026, 10, 18, 0, 0, 0, tzinfo=timezone.utc)


class FakeClock:
    """可控时钟。审批过期等场景必须用假时钟验证，不能依赖真实等待。"""

    def __init__(self, start: datetime = T0) -> None:
        self.now = start

    def advance(self, **kwargs) -> datetime:
        self.now += timedelta(**kwargs)
        return self.now


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


@pytest.fixture
def store() -> InMemoryStore:
    return InMemoryStore()


@pytest.fixture
def transitions(store: InMemoryStore) -> StateTransitionService:
    return StateTransitionService(store)


@pytest.fixture
def approvals(store: InMemoryStore) -> ApprovalRequestService:
    return ApprovalRequestService(store, RBACService(store))


@pytest.fixture
def gates(
    store: InMemoryStore, transitions: StateTransitionService, approvals: ApprovalRequestService
) -> GateEvaluator:
    return GateEvaluator(store, transitions, approvals)


@pytest.fixture
def router(store: InMemoryStore) -> LoopRouter:
    return LoopRouter(store)


@pytest.fixture
def rbac() -> RBACService:
    return RBACService()


@pytest.fixture
def delivery_run(transitions: StateTransitionService):
    """一个已推进到 ENGINEERING 的 DELIVERY Run。"""
    run = transitions.create_run(
        run_id="run-001",
        run_type=RunType.DELIVERY,
        project_id="proj-1",
        trigger_source="USER",
        config_snapshot_id="snap-001",
    )
    transitions.transition(run.run_id, target_status=RunStatus.RUNNING)
    transitions.transition(run.run_id, target_phase=RunPhase.PRODUCT)
    transitions.transition(run.run_id, target_phase=RunPhase.PRODUCT_AUDIT)
    transitions.transition(run.run_id, target_phase=RunPhase.ARCHITECTURE)
    transitions.transition(run.run_id, target_phase=RunPhase.G1)
    # 夹具仅提供门禁前现场，研发入口必须先由 GateEvaluator 放行。
    return transitions.store.get_run(run.run_id)


@pytest.fixture
def owner(rbac: RBACService) -> str:
    """项目所有者，真人主体。"""
    rbac.register_principal("human-owner", PrincipalType.HUMAN_USER, "idp://local")
    rbac.bind_role(
        principal_id="human-owner",
        role_id="project_owner",
        scope_type="project",
        scope_id="proj-1",
        valid_from=T0,
    )
    return "human-owner"


@pytest.fixture
def release_approver(rbac: RBACService) -> str:
    rbac.register_principal("human-approver", PrincipalType.HUMAN_USER, "idp://local")
    rbac.bind_role(
        principal_id="human-approver",
        role_id="release_approver",
        scope_type="project",
        scope_id="proj-1",
        valid_from=T0,
    )
    return "human-approver"


@pytest.fixture
def agent_backend(rbac: RBACService) -> str:
    """研发部门 Backend Agent，agent_service 主体。"""
    rbac.register_principal("agent-backend", PrincipalType.AGENT_SERVICE, "svc://internal")
    rbac.bind_role(
        principal_id="agent-backend",
        role_id="viewer",
        scope_type="project",
        scope_id="proj-1",
        valid_from=T0,
    )
    return "agent-backend"


@pytest.fixture
def engineering_caps() -> CapabilityResolver:
    """附录 A 的 engineering 部门配置。"""
    return CapabilityResolver(
        platform_default=CapabilitySet(grants=frozenset({Capability.REPO_READ})),
        department_max=CapabilitySet(
            grants=frozenset(
                {
                    Capability.REPO_READ,
                    Capability.WORKSPACE_WRITE,
                    Capability.TESTS_EXECUTE,
                    Capability.SANDBOX_EXECUTE,
                }
            )
        ),
        department_deny=frozenset({Capability.DEPLOY_PRODUCTION, Capability.SECRETS_MANAGE}),
    )


@pytest.fixture
def expert_caps() -> CapabilityResolver:
    """附录 A 的 expert 部门配置（含部署能力）。"""
    return CapabilityResolver(
        platform_default=CapabilitySet(
            grants=frozenset(
                {Capability.REPO_READ, Capability.DEPLOY_PRODUCTION}
            )
        ),
        department_max=CapabilitySet(
            grants=frozenset(
                {
                    Capability.REPO_READ,
                    Capability.DEPLOY_STAGING,
                    Capability.DEPLOY_PRODUCTION,
                    Capability.MEMORY_REVIEW,
                    Capability.RISK_WAIVER_APPROVE,
                }
            )
        ),
        department_deny=frozenset(),
    )


def gate_ids(*ids: GateId) -> list[str]:
    return [i.value for i in ids]