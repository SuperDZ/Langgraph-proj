from tools.tool_getTeamMembers import get_team_members
from tools.tool_getFullLog import get_full_log


"""
    工具注册表
    1. tool_definitions：给模型看的“工具说明书”
    2. tool_functions：真正的 Python 函数注册表
    3. get_tools：给某个 Agent 获取它需要的工具
    4. execute_tool：统一执行工具
    
"""


# 1. Tool Schema：给模型看的“工具说明书”
tool_definitions = {

    "get_full_log": {
        "type": "function",
        "name": "get_full_log",
        "description": "获取完整日志。当现有信息不足以判断故障根因时使用。",
        "parameters": {
            "type": "object",
            "properties": {
                "service_name": {
                    "type": "string",
                    "description": "服务名称"
                }
            },
            "required": ["service_name"],
            "additionalProperties": False
        }
    },

    "get_team_members": {
        "type": "function",
        "name": "get_team_members",
        "description": "获取指定团队的成员信息。",
        "parameters": {
            "type": "object",
            "properties": {
                "team_group": {
                    "type": "string",
                    "description": "团队名称，例如后端开发组、前端开发组、测试组"
                }
            },
            "required": ["team_group"],
            "additionalProperties": False
        }
    }
}


# 2. 真正的 Python 函数注册表
tool_functions = {
    "get_full_log": get_full_log,
    "get_team_members": get_team_members
}


# 3. 给某个 Agent 获取它需要的工具
def get_tools(*tool_names):
    return [
        tool_definitions[name]
        for name in tool_names
    ]


# 4. 统一执行工具
def execute_tool(tool_name: str, args: dict):

    tool_function = tool_functions.get(tool_name)

    if tool_function is None:
        raise ValueError(f"未知工具: {tool_name}")

    return tool_function(**args)