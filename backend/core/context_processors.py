"""Context Processors"""
from .settings import config


def config_context(request):
    """注入配置到模板上下文"""
    return {
        "config": config,
        "app_name": config.app_name,
        "app_version": config.app_version,
        "gitlab_url": config.gitlab["url"],
    }
