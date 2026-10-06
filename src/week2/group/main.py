"""支持项目根目录运行和直接运行本文件。"""

import argparse
import json
import sys
from pathlib import Path

if __package__ in (None, ""):
    sys.path.insert(0, str(Path(__file__).resolve().parents[2]))
    from week2.group.workflow import run_workflow
else:
    from .workflow import run_workflow


DEFAULT_SOURCE = Path(__file__).resolve().parents[1] / "test" / "test_codebase"


def main():
    parser = argparse.ArgumentParser(description="LangGraph 日志分析与任务分配")
    parser.add_argument("--log", default="somewhere errors in WebPageTranslateService")
    parser.add_argument("--src-base", default=str(DEFAULT_SOURCE))
    parser.add_argument("--max-rounds", type=int, default=8)
    args = parser.parse_args()
    result = run_workflow(args.log, args.src_base, max_rounds=args.max_rounds)
    print("日志分析结果：")
    print(json.dumps(result["log_analysis"], ensure_ascii=False, indent=2))
    print("任务分配结果：")
    print(json.dumps(result["task_assignment"], ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
