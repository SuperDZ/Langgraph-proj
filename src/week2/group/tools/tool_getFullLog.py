from langchain_core.tools import tool

service_log = [
    {
        "service_name": "WebPageTranslateService",
        "log": """
        Caused by: org.springframework.beans.factory.NoSuchBeanDefinitionException:
        No qualifying bean of type 'WebPageTranslateService' available
        """
    },
    {
        "service_name": "UserService",
        "log": """
        Caused by: org.springframework.beans.factory.BeanCreationException:
        Error creating bean with name 'userController':
        Unsatisfied dependency expressed through constructor parameter 0
        """
    }
]


@tool
def get_full_log(service_name: str) -> str:
    """获取指定服务的完整示例日志，现有信息不足以判断故障时使用。"""
    return next((entry["log"] for entry in service_log if entry["service_name"] == service_name), "未找到对应服务的日志。")