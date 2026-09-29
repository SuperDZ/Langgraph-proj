import json

"""
    Agent 运行器
    原理流程：
    1. 初始化 Context
    2. 调用模型，获取输出
    3. 检查输出中是否有工具调用
    4. 如果有工具调用，执行工具，并把结果加入 Context
    5. 重复 2-4，直到模型没有工具调用，返回最终结果
"""

def clean_json_text(text: str) -> str:
    """
    清理模型返回的 Markdown JSON 代码块，例如：
    ```json
    {...}
    ```
    """
    text = text.strip()

    if text.startswith("```json"):
        text = text[len("```json"):].strip()
    elif text.startswith("```"):
        text = text[3:].strip()

    if text.endswith("```"):
        text = text[:-3].strip()

    return text


def run_agent_with_tools(
    client,
    model,
    instructions,
    input_items,
    tools,
    execute_tool,
    text,
    max_rounds=8
):
    round_count = 0

    while True:
        round_count += 1

        print(f"\n[Round {round_count}]")

        if round_count > max_rounds:
            raise RuntimeError(
                f"Agent 工具调用超过最大轮数：{max_rounds}"
            )

        # 调用模型
        response = client.responses.create(
            model=model,
            instructions=instructions,
            input=input_items,
            tools=tools,
            text=text
        )

        # 找出模型这一轮请求调用的所有工具
        tool_calls = [
            item
            for item in response.output
            if item.type == "function_call"
        ]

        # 没有工具调用，说明模型已经得到最终结果
        if not tool_calls:
            print("[Agent] 执行完成，返回最终结果")

            output_text = response.output_text

            if not output_text:
                raise RuntimeError(
                    "模型没有返回最终文本，请检查 response.output"
                )

            print("[Output Text]", repr(output_text))

            # 清理 ```json ... ``` 包装
            output_text = clean_json_text(output_text)

            try:
                return json.loads(output_text)

            except json.JSONDecodeError as e:
                raise RuntimeError(
                    f"模型返回内容无法解析为 JSON：\n{output_text}"
                ) from e

        # 把模型这一轮完整输出加入 Context
        # 其中包括 function_call
        input_items.extend(response.output)

        # 逐个执行工具
        for item in tool_calls:

            # 参数解析失败 / 工具执行失败都不中断流程，
            # 而是把错误信息作为工具结果回喂给模型，
            # 让模型自行修正参数或更换工具重试。
            try:
                args = json.loads(item.arguments)
            except json.JSONDecodeError:
                args = None

            if args is None:
                print(f"[Tool Call] {item.name} 参数解析失败")
                tool_result = {
                    "success": False,
                    "error": f"工具参数不是合法 JSON：{item.arguments}"
                }
            else:
                print(f"[Tool Call] {item.name}")
                print(f"[Arguments] {args}")

                # Python 真正执行工具
                try:
                    tool_result = execute_tool(
                        item.name,
                        args
                    )
                except Exception as e:
                    tool_result = {
                        "success": False,
                        "error": f"工具执行失败：{type(e).__name__}: {e}"
                    }

            print(f"[Tool Result] {tool_result}")

            # 把工具执行结果加入 Context
            input_items.append({
                "type": "function_call_output",
                "call_id": item.call_id,
                "output": json.dumps(
                    tool_result,
                    ensure_ascii=False
                )
            })