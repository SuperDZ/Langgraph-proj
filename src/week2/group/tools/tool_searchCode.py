from langchain_core.tools import tool
from pathlib import Path

@tool
def search_code(src_base: str, keyword: str) -> dict:
    """
    在指定源码目录中搜索包含关键词的代码。

    Args:
        src_base: 源码根目录
        keyword: 类名、方法名或代码关键词
    """

    base_path = Path(src_base)

    # 目录不存在
    if not base_path.exists():
        return {
            "success": False,
            "src_base": src_base,
            "keyword": keyword,
            "count": 0,
            "results": [],
            "error": "源码目录不存在"
        }

    if not base_path.is_dir():
        return {
            "success": False,
            "src_base": src_base,
            "keyword": keyword,
            "count": 0,
            "results": [],
            "error": "src_base 不是目录"
        }

    keyword_lower = keyword.lower()

    results = []

    # 递归搜索所有 Java 文件
    for file_path in base_path.rglob("*.java"):

        try:
            code = file_path.read_text(
                encoding="utf-8"
            )
        except Exception:
            continue

        if (
            keyword_lower in file_path.name.lower()
            or keyword_lower in code.lower()
        ):
            results.append({
                "file_path": str(file_path),
                "code": code.strip()
            })# 这里直接使用 week1 真实的搜索逻辑

    return {
        "success": True,
        "src_base": src_base,
        "keyword": keyword,
        "count": len(results),
        "results": results,
        "error": None
    }