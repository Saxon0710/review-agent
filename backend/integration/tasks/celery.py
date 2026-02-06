"""Celery 配置和应用实例"""
import os
from celery import Celery

# 从环境变量读取 Redis 配置
REDIS_HOST = os.getenv("REVIEW_AGENT_REDIS_HOST", "redis")
REDIS_PORT = os.getenv("REVIEW_AGENT_REDIS_PORT", "6379")
REDIS_PASSWORD = os.getenv("REVIEW_AGENT_REDIS_PASSWORD", "")

# 构建 Redis URL
if REDIS_PASSWORD:
    redis_url = f"redis://:{REDIS_PASSWORD}@{REDIS_HOST}:{REDIS_PORT}/0"
else:
    redis_url = f"redis://{REDIS_HOST}:{REDIS_PORT}/0"

# Celery 配置
celery_config = {
    "broker_url": redis_url,
    "result_backend": redis_url,
    "task_serializer": "json",
    "accept_content": ["json"],
    "result_serializer": "json",
    "timezone": "Asia/Shanghai",
    "enable_utc": True,
    "task_track_started": True,
    "task_time_limit": 30 * 60,  # 30 分钟
    "task_soft_time_limit": 25 * 60,  # 25 分钟
    "worker_prefetch_multiplier": 1,
    "worker_max_tasks_per_child": 100,
}

# 创建 Celery 应用
app = Celery("review_agent")
app.conf.update(celery_config)

# 自动发现任务
app.autodiscover_tasks(["integration.tasks.jobs"])

# 定时任务配置
app.conf.beat_schedule = {
    "sync-active-projects": {
        "task": "integration.tasks.jobs.sync.sync_active_projects_task",
        "schedule": 15 * 60,  # 每 15 分钟
    },
    "cleanup-old-tasks": {
        "task": "integration.tasks.jobs.sync.cleanup_old_tasks_task",
        "schedule": 24 * 60 * 60,  # 每天
    },
}


@app.on_after_configure.connect
def setup_periodic_tasks(sender, **kwargs):
    """配置周期性任务"""
    pass
