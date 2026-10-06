"""按需创建模型；导入模块和运行离线测试不需要 API Key。"""

import os
from pathlib import Path

from dotenv import load_dotenv
from langchain_deepseek import ChatDeepSeek


def create_model() -> ChatDeepSeek:
    # 明确从项目根目录读取，避免从 group 启动时找不到 .env。
    load_dotenv(Path(__file__).resolve().parents[3] / ".env")
    api_key = os.getenv("DEEPSEEK_API_KEY")
    if not api_key:
        raise ValueError("请在环境变量或项目根目录 .env 中设置 DEEPSEEK_API_KEY")
    return ChatDeepSeek(
        model=os.getenv("DEEPSEEK_MODEL", "deepseek-chat"),
        api_key=api_key,
        temperature=0,
        timeout=60,
        max_retries=2,
    )
