"""
健康检查路由
"""
from fastapi import APIRouter
from config.settings import config

router = APIRouter()


@router.get("/health/live")
async def liveness():
    """存活检查"""
    return {"status": "alive"}


@router.get("/health/ready")
async def readiness():
    """就绪检查"""
    # TODO: 添加数据库连接检查
    return {
        "status": "ready",
        "version": config.app_version,
        "environment": config.env,
    }


@router.get("/config")
async def get_config():
    """获取公开配置"""
    return {
        "app_name": config.app_name,
        "version": config.app_version,
        "gitlab_url": config.gitlab["url"],
        "supported_review_types": [
            "review",
            "describe",
            "improve",
            "question",
            "update_changelog",
            "generate_labels",
        ],
    }
