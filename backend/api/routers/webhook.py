"""
GitLab Webhook 路由
处理来自 GitLab 的 Webhook 事件
"""
from fastapi import APIRouter, Request, Depends, HTTPException, status
from pydantic import BaseModel
from typing import Optional, Any
import logging

from api.dependencies import verify_gitlab_webhook
from config.settings import config
from integration.tasks.celery import app

logger = logging.getLogger(__name__)
router = APIRouter()


# ========== Webhook 请求模型 ==========
class GitLabWebhookPayload(BaseModel):
    """GitLab Webhook 载荷"""
    object_kind: str
    event_type: Optional[str] = None

    # MR 事件
    object_attributes: Optional[dict] = None
    merge_request: Optional[dict] = None

    # Push 事件
    ref: Optional[str] = None
    checkout_sha: Optional[str] = None
    commits: Optional[list] = None
    total_commits_count: Optional[int] = None

    # 评论事件
    note: Optional[dict] = None

    # 用户信息
    user: Optional[dict] = None

    # 项目信息
    project: Optional[dict] = None


# ========== Webhook 端点 ==========
@router.post("/webhook/gitlab")
async def gitlab_webhook(
    request: Request,
    verified: bool = Depends(verify_gitlab_webhook),
):
    """
    GitLab Webhook 接收端点

    支持的事件类型:
    - merge_request: MR 创建/更新/合并/关闭
    - note: 评论事件 (用于触发审查命令)
    - push: Push 事件 (监听指定分支的代码推送)
    """
    try:
        payload = await request.json()
        logger.info(f"Received GitLab webhook: {payload.get('object_kind')}")

        # 验证载荷
        webhook_payload = GitLabWebhookPayload(**payload)

        # 根据 event_type 分发到不同的 Celery 任务
        event_type = payload.get("object_kind")

        if event_type == "merge_request":
            # 使用 Celery 异步处理 MR 事件
            app.send_task(
                "integration.tasks.jobs.webhook.process_merge_request_event",
                args=[payload],
            )
            logger.info(f"MR event queued for processing")

        elif event_type == "note":
            # 使用 Celery 异步处理评论事件
            app.send_task(
                "integration.tasks.jobs.webhook.process_note_event",
                args=[payload],
            )
            logger.info(f"Note event queued for processing")

        elif event_type == "push":
            # 使用 Celery 异步处理 Push 事件
            app.send_task(
                "integration.tasks.jobs.webhook.process_push_event",
                args=[payload],
            )
            logger.info(f"Push event queued for processing")

        else:
            logger.info(f"Unsupported event type: {event_type}")
            return {"status": "ignored", "message": f"Unsupported event type: {event_type}"}

        return {"status": "accepted", "message": "Webhook queued for processing"}

    except Exception as e:
        logger.error(f"Error processing webhook: {e}", exc_info=True)
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid webhook payload: {str(e)}",
        )
