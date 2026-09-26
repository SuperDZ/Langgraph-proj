from client_manager import client
from ..tool_execute import execute_tool, get_tools
from ..agent_runner import run_agent_with_tools
import json

"""
    日志分析agent
"""

# 定义日志结构
log_schema = {
    "format": {
        "type": "json_schema",
        "name": "log_analysis",
        "schema": {
            "type": "object",

            "properties": {
                "error_type": {
                    "type": "string"
                },

                "root_cause": {
                    "type": "string"
                },

                "possible_causes": {
                    "type": "array",
                    "items": {
                        "type": "string"
                    },
                    "maxItems": 3
                },

                "confidence": {
                    "type": "number",
                    "minimum": 0,
                    "maximum": 1
                },

                "suggestions": {
                    "type": "array",
                    "items": {
                        "type": "string"
                    },
                    "maxItems": 3
                }
            },

            "required": [
                "error_type",
                "root_cause",
                "possible_causes",
                "confidence",
                "suggestions"
            ],

            "additionalProperties": False
        }
    }
}
def review_log(log_receive: str, src_base: str):
    input_items = [
        {
            "role": "user",
            "content": f"""
                            请分析下面的信息：
                            {log_receive}

                            源码根目录：
                            {src_base}
                        """
        }
    ]
    return run_agent_with_tools(
        client=client,
        model="deepseek-v4-pro",
        instructions=f"""
                    你是一个专业的 Java 日志分析师。

                    你的任务是：
                    1. 判断错误类型
                    2. 找出真正根因
                    3. 给出排查建议

                    如果当前信息不足以确定根因，
                    不要猜测，调用 get_full_log 获取完整日志。

                    如果需要查看源码确认根因
                    调用 search_code 在指定代码仓库中搜索类名、方法名或其他源码关键字。
                    
                    源码根目录固定为：
                    {src_base}
                    调用 search_code 时必须使用这个 src_base，
                    不要自行猜测其他源码目录。                    
                    """,
        input_items=input_items,
        tools=get_tools("get_full_log", "search_code"),
        execute_tool=execute_tool,
        text=log_schema
    )