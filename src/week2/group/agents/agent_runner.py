"""用图中的边实现 Agent Loop，不再手写 while 和工具分发器。"""

import json
from typing import Annotated

from langchain_core.messages import AIMessage, AnyMessage, SystemMessage
from langgraph.graph import END, START, StateGraph, add_messages
from langgraph.prebuilt import ToolNode, tools_condition
from pydantic import BaseModel
from typing_extensions import TypedDict


class AgentState(TypedDict):
    messages: Annotated[list[AnyMessage], add_messages]
    rounds: int
    result: dict


def build_tool_agent(model, tools, instructions: str,
                     output_schema: type[BaseModel], max_rounds: int = 8):
    """构建 model → tools → model 循环，再生成经过校验的 JSON 结果。"""
    if max_rounds < 1:
        raise ValueError("max_rounds 必须大于 0")
    tool_model = model.bind_tools(tools)
    # 输出节点不绑定业务工具，避免结果格式与工具调用互相干扰。
    structured_model = model.with_structured_output(output_schema, method="json_mode")
    system_message = SystemMessage(content=instructions)

    def call_model(state: AgentState):
        rounds = state.get("rounds", 0)
        if rounds >= max_rounds:
            raise RuntimeError(f"Agent 工具调用超过最大轮数：{max_rounds}")
        response = tool_model.invoke([system_message, *state["messages"]])
        if not isinstance(response, AIMessage) or response.invalid_tool_calls:
            raise RuntimeError("模型没有返回有效的 AIMessage 或工具参数不是合法 JSON")
        return {"messages": [response], "rounds": rounds + 1}

    def finalize(state: AgentState):
        schema_text = json.dumps(output_schema.model_json_schema(), ensure_ascii=False)
        response = structured_model.invoke([
            SystemMessage(content=instructions + "\n只输出符合下列 schema 的 JSON：\n" + schema_text),
            *state["messages"],
        ])
        result = output_schema.model_validate(response).model_dump()
        return {"result": result}

    graph = StateGraph(AgentState)
    graph.add_node("model", call_model)
    graph.add_node("tools", ToolNode(tools, handle_tool_errors=True))
    graph.add_node("finalize", finalize)
    graph.add_edge(START, "model")
    graph.add_conditional_edges("model", tools_condition,
                                {"tools": "tools", END: "finalize"})
    graph.add_edge("tools", "model")
    graph.add_edge("finalize", END)
    return graph.compile()
