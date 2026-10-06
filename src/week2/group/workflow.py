"""外层图固定业务顺序，内层图自主决定工具调用。"""

import json
from pathlib import Path

from langchain_core.messages import HumanMessage
from langgraph.graph import END, START, StateGraph
from typing_extensions import TypedDict

from .agents.log_reviewer import build_log_reviewer
from .agents.team_leader import build_team_leader, validate_assignments
from .client_manager import create_model


class WorkflowState(TypedDict):
    log_receive: str
    src_base: str
    log_analysis: dict
    task_assignment: dict


def build_workflow(model=None, max_rounds: int = 8):
    model = model if model is not None else create_model()
    leader = build_team_leader(model, max_rounds)

    def analyze_log(state: WorkflowState):
        reviewer = build_log_reviewer(model, state["src_base"], max_rounds)
        result = reviewer.invoke(
            {"messages": [HumanMessage(content=state["log_receive"])], "rounds": 0},
            config={"recursion_limit": 2 * max_rounds + 3},
        )
        return {"log_analysis": result["result"]}

    def assign_tasks(state: WorkflowState):
        result = leader.invoke(
            {"messages": [HumanMessage(content=json.dumps(
                state["log_analysis"], ensure_ascii=False))], "rounds": 0},
            config={"recursion_limit": 2 * max_rounds + 3},
        )
        return {"task_assignment": validate_assignments(result)}

    graph = StateGraph(WorkflowState)
    graph.add_node("log_reviewer", analyze_log)
    graph.add_node("team_leader", assign_tasks)
    graph.add_edge(START, "log_reviewer")
    graph.add_edge("log_reviewer", "team_leader")
    graph.add_edge("team_leader", END)
    return graph.compile()


def run_workflow(log_receive: str, src_base: str, model=None, max_rounds: int = 8):
    graph = build_workflow(model, max_rounds)
    return graph.invoke({"log_receive": log_receive,
                         "src_base": str(Path(src_base).expanduser().resolve())})
