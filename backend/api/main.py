"""
FastAPI 主应用
处理 Webhook、AI 服务和异步任务
"""
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from contextlib import asynccontextmanager
import logging
import django
import os

from config.settings import config

# 配置日志
logging.basicConfig(level=config.logging['level'])
logger = logging.getLogger(__name__)

# 设置 Django 环境
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'settings.base')
django.setup()


@asynccontextmanager
async def lifespan(app: FastAPI):
    """应用生命周期管理"""
    logger.info(f"Starting {config.app_name} v{config.app_version} (FastAPI)")
    yield
    logger.info(f"Shutting down {config.app_name} (FastAPI)")


# 创建 FastAPI 应用
app = FastAPI(
    title="Review Agent API",
    description="PR 代码审查服务 - 基于 AI 的 GitLab MR 审查工具",
    version=config.app_version,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
    lifespan=lifespan,
)

# 配置 CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=config.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ========== 根路径 ==========
@app.get("/")
async def root():
    """根路径 - 服务状态"""
    return {
        "service": config.app_name,
        "version": config.app_version,
        "status": "ok",
        "api_docs": "/api/docs",
    }


# ========== 健康检查 ==========
@app.get("/health")
async def health_check():
    """健康检查端点"""
    return {
        "status": "healthy",
        "version": config.app_version,
        "environment": config.env,
    }


# ========== 异常处理器 ==========
@app.exception_handler(Exception)
async def global_exception_handler(request, exc):
    """全局异常处理"""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "error": "Internal Server Error",
            "message": str(exc) if config.debug else "An error occurred",
        },
    )


# ========== 导入路由 ==========
from api.routers import webhook, review, health, tasks

# 注册路由
app.include_router(health.router, tags=["Health"])
app.include_router(webhook.router, prefix="/api/v1", tags=["Webhook"])
app.include_router(review.router, prefix="/api/v1", tags=["Review"])
app.include_router(tasks.router, prefix="/api/v1", tags=["Tasks"])
