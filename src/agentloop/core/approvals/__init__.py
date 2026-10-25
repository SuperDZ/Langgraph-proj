"""审批与权限：RBAC、G1 人工确认、发布授权、风险豁免。"""

from .approval_requests import (
    GATE_EVALUATOR,
    ApprovalError,
    ApprovalRequestService,
    compute_input_digest,
)
from .rbac import (
    AGENT_FORBIDDEN_ROLES,
    CAPABILITY_REGISTRY,
    LEGACY_CAPABILITY_MAP,
    ROLE_DEFINITIONS,
    AccessDenied,
    Capability,
    CapabilityResolver,
    ConfigError,
    RBACService,
    assert_capability,
    resolve_capability,
)

__all__ = [
    "AGENT_FORBIDDEN_ROLES",
    "AccessDenied",
    "ApprovalError",
    "ApprovalRequestService",
    "CAPABILITY_REGISTRY",
    "Capability",
    "CapabilityResolver",
    "ConfigError",
    "GATE_EVALUATOR",
    "LEGACY_CAPABILITY_MAP",
    "RBACService",
    "ROLE_DEFINITIONS",
    "assert_capability",
    "compute_input_digest",
    "resolve_capability",
]