from agents.dev_group.log_reviewer import review_log
from agents.team_leader import task_management
from pathlib import Path


log_recive = """somewhere errors in WebPageTranslateService"""

src_base = str(
    Path(__file__).resolve().parent.parent
    / "test"
    / "test_codebase"
)




def main():
    #agent 1
    analysis_result = review_log(log_recive, src_base)
    print("日志分析结果：")
    print(analysis_result)
    

    #agent 2
    task_assignment_result = task_management(analysis_result)
    print("任务分配结果：")
    print(task_assignment_result)


if __name__ == "__main__":
    main()