import json

from langchain_core.messages import HumanMessage, ToolMessage

from ..client_manager import create_model
from ..schemas import AssignmentResult
from ..tools import get_team_members
from .agent_runner import build_tool_agent


def build_team_leader(model, max_rounds: int = 8):
    return build_tool_agent(
        model, [get_team_members],
        instructions=(
            "你是团队 Leader，根据日志分析结果判断应该由哪个团队处理。"
            "分配前必须调用 get_team_members，按成员技能和经验分配具体排查任务。"
            "只分配给工具实际返回的成员；未找到成员时返回空 task_assignments。"
            "不要把推测的根因描述成已确认事实，用中文回答。"
        ),
        output_schema=AssignmentResult, max_rounds=max_rounds,
    )


def validate_assignments(state: dict) -> dict:
    """防止未查询成员或分配给工具从未返回的人。"""
    members = set()
    queried = False
    for message in state["messages"]:
        if isinstance(message, ToolMessage) and message.name == "get_team_members":
            if message.status == "error":
                continue
            data = json.loads(message.content)
            queried = True
            members.update(member["name"] for member in data)
    if not queried:
        raise RuntimeError("任务分配前必须成功调用 get_team_members")
    result = state["result"]
    for assignment in result["task_assignments"]:
        if assignment["team_member"] not in members:
            raise RuntimeError("任务分配包含未从工具查到的成员")
    return result


def task_management(log_analysis: dict, model=None, max_rounds: int = 8):
    """保留 week1 的函数入口，内部执行 LangGraph 子图。"""
    graph = build_team_leader(model if model is not None else create_model(), max_rounds)
    state = graph.invoke({"messages": [HumanMessage(
        content=json.dumps(log_analysis, ensure_ascii=False))], "rounds": 0},
        config={"recursion_limit": 2 * max_rounds + 3})
    return validate_assignments(state)
