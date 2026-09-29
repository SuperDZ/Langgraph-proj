from client_manager import client
from .agent_runner import run_agent_with_tools
from .tool_execute import execute_tool, get_tools
import json


"""
    团队 Leader Agent
    1. 根据日志分析结果判断应该由哪个团队处理。
    2. 在给成员分配任务之前，需要了解该团队有哪些成员，调用 get_team_members。
    3. 拿到成员信息后，根据成员技能和经验选择最合适的人负责该任务。
"""

assignment_schema = {
    "format": {
        "type": "json_schema",
        "name": "task_assignment",
        "schema": {
            "type": "object",
            "properties": {
                "task_assignments": {
                    "type": "array",
                    "items": {
                        "type": "object",
                        "properties": {
                            "team_member": {
                                "type": "string"
                            },
                            "task_description": {
                                "type": "string"
                            }
                        },
                        "required": [
                            "team_member",
                            "task_description"
                        ],
                        "additionalProperties": False
                    }
                }
            },
            "required": ["task_assignments"],
            "additionalProperties": False
        }
    }
}


def task_management(log_analysis: dict):

    input_items = [
        {
            "role": "user",
            "content": f"""
                        请根据下面的日志分析结果分配任务：
                        {json.dumps(log_analysis, ensure_ascii=False)}
                        """
        }
    ]

    return run_agent_with_tools(
        client=client,
        model="deepseek-v4-pro",
        instructions="""
                    你是一个团队 Leader。
                    根据故障分析结果判断应该由哪个团队处理。
                    在给成员分配任务之前，需要了解该团队有哪些成员，
                    调用 get_team_members。
                    拿到成员信息后，
                    根据成员技能和经验选择最合适的人负责该任务。
                    """,
        input_items=input_items,
        tools=get_tools("get_team_members"),
        execute_tool=execute_tool,
        text=assignment_schema
    )