
teams = [
    {
        "team_group": "后端开发组",
        "team_members": [
            {
                "name": "张三",
                "skills": ["Java", "Spring", "Redis"],
                "experience": "5年后端开发"
            },
            {
                "name": "李四",
                "skills": ["Java", "MySQL", "Docker"],
                "experience": "3年后端开发"
            }
        ]
    },
    {
        "team_group": "前端开发组",
        "team_members": [
            {
                "name": "赵六",
                "skills": ["JavaScript", "Vue"],
                "experience": "2年前端开发"
            },
            {
                "name": "钱七",
                "skills": ["JavaScript", "React"],
                "experience": "4年前端开发"
            }
        ]
    },
    {
        "team_group": "测试组",
        "team_members": [
            {
                "name": "孙八",
                "skills": ["自动化测试", "性能测试"],
                "experience": "3年测试经验"
            },
            {
                "name": "周九",
                "skills": ["手动测试", "接口测试"],
                "experience": "5年测试经验"
            }
        ]
    }
]




def get_team_members(team_group: str):
    for team in teams:
        if team["team_group"] == team_group:
            return team["team_members"]
    return []