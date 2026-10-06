import os
import json
from dotenv import load_dotenv
from langchain_deepseek import ChatDeepSeek
from langchain_core.messages import HumanMessage, ToolMessage
from tools.tool_searchCode import search_code


def main():
    load_dotenv()  # Load environment variables from .env file

    model = ChatDeepSeek(
        model="deepseek-chat",
        temperature=0,
        api_key=os.getenv("DEEPSEEK_API_KEY")
    )

    # 把工具告诉模型
    model_with_tools = model.bind_tools([search_code])

    # 消息历史
    messages = [
        HumanMessage(
            content="请帮我查找 WebPageTranslateService 的源码，"
                    "源码目录是 test/test_codebase"
        )
    ]

    while True:

        response = model_with_tools.invoke(messages)

        messages.append(response)

        print("\n模型回答：")
        print(response.content)

        # 没有工具调用 → Agent 完成
        if not response.tool_calls:
            print("\n最终回答：")
            print(response.content)
            break

        # 有工具调用 → 执行
        for tool_call in response.tool_calls:

            if tool_call["name"] == "search_code":

                result = search_code.invoke(
                    tool_call["args"]
                )

                print("\nTool Result：")
                print(result)

                messages.append(
                    ToolMessage(
                        content=json.dumps(
                            result,
                            ensure_ascii=False
                        ),
                        tool_call_id=tool_call["id"]
                    )
                )

if __name__ == "__main__":
    main()