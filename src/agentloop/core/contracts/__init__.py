"""严格输入/输出/事件 Schema。

所有面向 Agent 和外部调用的契约都基于 ``StrictModel``：
``extra="forbid"`` 保证 Agent 无法通过附加字段注入 ``target_leader``、
``final_gate_result`` 等服务端专属字段（规范 §7.2 / REQ-019）。
"""

from .enums import *  # noqa: F401,F403  — 枚举集中定义于enums.py

__all__ = ["enums"]