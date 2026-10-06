"""离线使用脚本模型驱动真实 LangGraph 和 ToolNode，不替换工具实现。"""

import json
from pathlib import Path

import httpx
import pytest
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.tools import BaseTool
from langchain_deepseek import ChatDeepSeek
from pydantic import ValidationError

from week2.group.agents.agent_runner import build_tool_agent
from week2.group.agents.log_reviewer import build_log_reviewer, review_log
from week2.group.agents.team_leader import task_management
from week2.group.client_manager import create_model
from week2.group.schemas import LogAnalysis
from week2.group.tools import get_full_log, get_team_members, search_code
from week2.group.workflow import run_workflow

SOURCE = Path(__file__).parent / "test_codebase"
ANALYSIS = {
    "error_type": "NoSuchBeanDefinitionException",
    "root_cause": "Spring 容器没有注册 WebPageTranslateService",
    "possible_causes": ["源码缺少 @Service 注解"],
    "confidence": 0.9,
    "suggestions": ["添加 @Service 并验证组件扫描范围"],
}
ASSIGNMENT = {"task_assignments": [
    {"team_member": "张三", "task_description": "检查服务注册及扫描范围"}
]}


def call(name, args, call_id="call_1"):
    return {"name": name, "args": args, "id": call_id, "type": "tool_call"}


class ScriptedModel:
    def __init__(self, scripts, results):
        self.scripts = scripts
        self.results = results
        self.histories = {}
        self.final_histories = {}
        self.bound_tools = {}

    def bind_tools(self, tools):
        key = "reviewer" if tools[0].name == "get_full_log" else "leader"
        responses = iter(self.scripts[key])
        self.bound_tools[key] = tools
        owner = self

        class BoundModel:
            def invoke(self, messages):
                owner.histories.setdefault(key, []).append(list(messages))
                return next(responses)

        return BoundModel()

    def with_structured_output(self, schema, method):
        assert method == "json_mode"
        key = "reviewer" if schema is LogAnalysis else "leader"
        owner = self

        class StructuredModel:
            def invoke(self, messages):
                owner.final_histories[key] = list(messages)
                return owner.results[key]

        return StructuredModel()


def reviewer_model(calls, result=None):
    return ScriptedModel({"reviewer": calls}, {"reviewer": result or ANALYSIS})


def test_all_tools_are_langchain_tools():
    for tool in (get_full_log, get_team_members, search_code):
        assert isinstance(tool, BaseTool)
    assert "NoSuchBeanDefinitionException" in get_full_log.invoke(
        {"service_name": "WebPageTranslateService"})
    assert get_team_members.invoke({"team_group": "后端开发组"})[0]["name"] == "张三"
    assert get_team_members.invoke({"team_group": "不存在的团队"}) == []


def test_source_search_from_unrelated_working_directory(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    result = search_code.invoke({"src_base": str(SOURCE.resolve()),
                                 "keyword": "WebPageTranslateService"})
    assert result["success"] and result["count"] == 2
    assert any("public class WebPageTranslateService" in r["code"]
               for r in result["results"])


@pytest.mark.parametrize("kind,error", [
    ("missing", "源码目录不存在"), ("file", "src_base 不是目录"),
    ("empty", "keyword 不能为空"),
])
def test_source_search_errors(tmp_path, kind, error):
    path = tmp_path / "missing"
    if kind == "file":
        path.write_text("test")
    elif kind == "empty":
        path = tmp_path
    result = search_code.invoke({"src_base": str(path),
                                 "keyword": " " if kind == "empty" else "Service"})
    assert not result["success"] and result["error"] == error


def test_workflow_calls_real_tools_and_passes_analysis():
    model = ScriptedModel({
        "reviewer": [AIMessage(content="", tool_calls=[
            call("get_full_log", {"service_name": "WebPageTranslateService"}, "log"),
            call("search_code", {"keyword": "WebPageTranslateService"}, "code"),
        ]), AIMessage(content="已收集证据")],
        "leader": [AIMessage(content="", tool_calls=[
            call("get_team_members", {"team_group": "后端开发组"}, "team")
        ]), AIMessage(content="已查询成员")],
    }, {"reviewer": ANALYSIS, "leader": ASSIGNMENT})
    result = run_workflow("服务启动失败", str(SOURCE), model=model)
    assert result["log_analysis"] == ANALYSIS
    assert result["task_assignment"] == ASSIGNMENT
    assert json.loads(model.histories["leader"][0][1].content) == ANALYSIS
    messages = model.histories["reviewer"][1]
    tool_messages = [m for m in messages if isinstance(m, ToolMessage)]
    assert {m.tool_call_id for m in tool_messages} == {"log", "code"}
    assert json.loads(next(m.content for m in tool_messages if m.name == "search_code"))["count"] == 2
    assert [t.name for t in model.bound_tools["leader"]] == ["get_team_members"]
    assert any(isinstance(m, ToolMessage) for m in model.final_histories["reviewer"])


def test_source_root_cannot_be_overridden(tmp_path):
    model = reviewer_model([AIMessage(content="", tool_calls=[call(
        "search_code", {"keyword": "WebPageTranslateService", "src_base": str(SOURCE)})
    ]), AIMessage(content="检索失败")])
    missing = str(tmp_path / "missing")
    review_log("检查源码", missing, model=model)
    bound_search = model.bound_tools["reviewer"][1]
    assert set(bound_search.args) == {"keyword"}
    tool_result = next(m for m in model.histories["reviewer"][1]
                       if isinstance(m, ToolMessage))
    assert json.loads(tool_result.content)["src_base"] == missing
    assert json.loads(tool_result.content)["error"] == "源码目录不存在"


@pytest.mark.parametrize("tool_call", [
    call("unknown_tool", {}), call("get_full_log", {}),
])
def test_tool_errors_return_to_model(tool_call):
    model = reviewer_model([AIMessage(content="", tool_calls=[tool_call]),
                            AIMessage(content="参数有误，停止调用")])
    assert review_log("启动失败", str(SOURCE), model=model) == ANALYSIS
    assert next(m for m in model.histories["reviewer"][1]
                if isinstance(m, ToolMessage)).status == "error"


def test_runtime_tool_exception_returns_to_model():
    from langchain_core.tools import tool

    @tool
    def get_full_log(service_name: str) -> str:
        """模拟日志源不可用。"""
        raise OSError("日志源不可用")

    model = reviewer_model([AIMessage(content="", tool_calls=[
        call("get_full_log", {"service_name": "Test"})]), AIMessage(content="停止")])
    graph = build_tool_agent(model, [get_full_log], "分析日志", LogAnalysis)
    graph.invoke({"messages": [HumanMessage(content="失败")], "rounds": 0})
    message = next(m for m in model.histories["reviewer"][1] if isinstance(m, ToolMessage))
    assert message.status == "error" and "日志源不可用" in message.content


def test_no_tool_call_finishes_directly():
    model = reviewer_model([AIMessage(content="现有日志已足够")])
    assert review_log("完整日志", str(SOURCE), model=model) == ANALYSIS
    assert len(model.histories["reviewer"]) == 1


def test_max_rounds_stops_endless_tool_calls():
    model = reviewer_model([AIMessage(content="", tool_calls=[
        call("get_full_log", {"service_name": "UserService"}, str(i))
    ]) for i in range(2)])
    with pytest.raises(RuntimeError, match="最大轮数：2"):
        review_log("循环调用", str(SOURCE), model=model, max_rounds=2)
    assert len(model.histories["reviewer"]) == 2


@pytest.mark.parametrize("patch", [
    {"confidence": 2}, {"possible_causes": ["x"] * 4}, {"extra": "unexpected"},
])
def test_invalid_structured_output_is_rejected(patch):
    model = reviewer_model([AIMessage(content="完成")], {**ANALYSIS, **patch})
    with pytest.raises(ValidationError):
        review_log("错误日志", str(SOURCE), model=model)


@pytest.mark.parametrize("queried,member", [(False, "张三"), (True, "虚构成员")])
def test_leader_rejects_missing_lookup_or_unknown_member(queried, member):
    calls = []
    if queried:
        calls.append(AIMessage(content="", tool_calls=[
            call("get_team_members", {"team_group": "后端开发组"})]))
    calls.append(AIMessage(content="完成"))
    model = ScriptedModel({"leader": calls}, {"leader": {"task_assignments": [
        {"team_member": member, "task_description": "排查"}]}})
    with pytest.raises(RuntimeError, match="必须成功调用|未从工具查到"):
        task_management(ANALYSIS, model=model)


def test_invalid_tool_call_json_is_rejected():
    model = reviewer_model([AIMessage(content="", invalid_tool_calls=[
        {"name": "search_code", "args": "{", "id": "bad", "error": "invalid JSON"}
    ])])
    with pytest.raises(RuntimeError, match="合法 JSON"):
        review_log("错误日志", str(SOURCE), model=model)


def test_model_is_created_lazily_without_key(monkeypatch):
    import week2.group.client_manager as manager
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    monkeypatch.setattr(manager, "load_dotenv", lambda *args: None)
    with pytest.raises(ValueError, match="DEEPSEEK_API_KEY"):
        create_model()


def test_actual_deepseek_adapter_uses_tools_and_json_mode(monkeypatch):
    # 模拟传输测试不使用执行环境的网络代理。
    for name in ("HTTP_PROXY", "HTTPS_PROXY", "ALL_PROXY", "http_proxy", "https_proxy", "all_proxy"):
        monkeypatch.delenv(name, raising=False)
    requests = []

    def handler(request):
        body = json.loads(request.content)
        requests.append(body)
        if "tools" in body:
            message = {"role": "assistant", "content": "已分析"}
        else:
            message = {"role": "assistant", "content": json.dumps(ANALYSIS)}
        return httpx.Response(200, json={
            "id": "test", "object": "chat.completion", "created": 0,
            "model": "deepseek-chat", "choices": [
                {"index": 0, "message": message, "finish_reason": "stop"}],
        })

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        model = ChatDeepSeek(model="deepseek-chat", api_key="offline-test-key",
                             http_client=client, max_retries=0)
        assert review_log("完整日志", str(SOURCE), model=model) == ANALYSIS
    assert {t["function"]["name"] for t in requests[0]["tools"]} == {"get_full_log", "search_code"}
    assert "tools" not in requests[1]
    assert requests[1]["response_format"] == {"type": "json_object"}


def test_graph_topology_and_invalid_rounds():
    model = reviewer_model([])
    graph = build_log_reviewer(model, str(SOURCE))
    edges = {(edge.source, edge.target) for edge in graph.get_graph().edges}
    assert ("model", "tools") in edges and ("tools", "model") in edges
    assert ("model", "finalize") in edges
    with pytest.raises(ValueError, match="max_rounds"):
        build_log_reviewer(model, str(SOURCE), max_rounds=0)
