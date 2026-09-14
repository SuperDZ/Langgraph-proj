from agents.log_reviewer import review_log
from agents.team_leader import task_management

log_recive = """somewhere errors in WebPageTranslateService"""


def main():
    #agent 1
    analysis_result = review_log(log_recive)
    print("日志分析结果：")
    print(analysis_result)
    

    #agent 2
    task_assignment_result = task_management(analysis_result)
    print("任务分配结果：")
    print(task_assignment_result)


if __name__ == "__main__":
    main()