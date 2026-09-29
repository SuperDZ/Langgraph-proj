from pathlib import Path


# 返回结果保护阈值：防止大文件 / 多命中把模型 context 打爆
MAX_FILES = 5             # 最多返回的文件数
CONTEXT_LINES = 5         # 命中行前后保留的上下文行数
MAX_SNIPPET_CHARS = 3000  # 单文件代码片段最大字符数


def _build_snippet(code: str, keyword_lower: str, match_by_name: bool):
    """
    从源码中提取命中行附近的代码片段。

    :return: (matched_line_numbers, snippet_text)
    """
    lines = code.splitlines()

    # 仅文件名命中：返回文件头部让模型了解文件内容
    if match_by_name:
        head = lines[:30]
        snippet = "\n".join(
            f"{i + 1}: {line}" for i, line in enumerate(head)
        )
        if len(lines) > 30:
            snippet += "\n...(仅展示文件前 30 行)"
        return [], snippet

    matched = [
        i for i, line in enumerate(lines)
        if keyword_lower in line.lower()
    ]

    # 合并重叠的上下文窗口
    ranges = []
    for i in matched:
        start = max(0, i - CONTEXT_LINES)
        end = min(len(lines), i + CONTEXT_LINES + 1)
        if ranges and start <= ranges[-1][1]:
            ranges[-1][1] = max(ranges[-1][1], end)
        else:
            ranges.append([start, end])

    parts = [
        "\n".join(f"{ln + 1}: {lines[ln]}" for ln in range(start, end))
        for start, end in ranges
    ]
    snippet = "\n...\n".join(parts)

    if len(snippet) > MAX_SNIPPET_CHARS:
        snippet = snippet[:MAX_SNIPPET_CHARS] + "\n...(片段过长已截断)"

    # 行号从 1 开始
    return [i + 1 for i in matched], snippet


def search_code(src_base: str, keyword: str):
    """
    在指定源码根目录中递归搜索代码。
    只返回命中行附近的代码片段，避免占用过多模型上下文。

    :param src_base: 源码根目录
    :param keyword: 类名、方法名或其他源码关键字
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
    total_matched_files = 0

    # 递归搜索所有 Java 文件
    for file_path in base_path.rglob("*.java"):

        try:
            code = file_path.read_text(
                encoding="utf-8"
            )
        except Exception:
            continue

        match_by_name = keyword_lower in file_path.name.lower()
        match_by_content = keyword_lower in code.lower()

        if not (match_by_name or match_by_content):
            continue

        total_matched_files += 1

        # 超过数量上限的文件只计数，不再提取内容
        if len(results) >= MAX_FILES:
            continue

        matched_lines, snippet = _build_snippet(
            code, keyword_lower, match_by_name and not match_by_content
        )

        results.append({
            "file_path": str(file_path),
            "matched_lines": matched_lines,
            "snippet": snippet
        })

    return {
        "success": True,
        "src_base": src_base,
        "keyword": keyword,
        "count": len(results),
        "total_matched_files": total_matched_files,
        "truncated": total_matched_files > len(results),
        "results": results,
        "error": None
    }
