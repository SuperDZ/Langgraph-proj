"""确定性责任路由。

LoopRouter 是纯代码，不调用 LLM（规范 §2.7 / REQ-019）。
"""

from .loop_router import ROUTER_POLICY_VERSION, LoopRouter, OwnershipTable

__all__ = ["ROUTER_POLICY_VERSION", "LoopRouter", "OwnershipTable"]