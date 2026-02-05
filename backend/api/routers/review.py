"""
审查 API 路由
提供手动触发审查、查询状态等接口
"""
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from typing import Optional, List
from uuid import UUID
import logging
from datetime import datetime

from api.dependencies import get_current_user, get_current_user_optional
from config.settings import config
from core.models import ReviewTask, PullRequest, GitLabProject, GitLabUser
from integration.tasks.celery import app

logger = logging.getLogger(__name__)
router = APIRouter()


# ========== 请求/响应模型 ==========
class ReviewRequest(BaseModel):
    """手动触发审查请求"""
    project_id: int = Field(..., description="GitLab 项目 ID")
    mr_iid: int = Field(..., description="MR IID")
    review_type: str = Field(
        default="review",
        description="审查类型: review, describe, improve, question",
    )
    options: Optional[dict] = Field(default=None, description="额外选项")


class ReviewResponse(BaseModel):
    """审查响应"""
    task_id: UUID
    status: str
    review_type: str
    message: str


class TaskStatusResponse(BaseModel):
    """任务状态响应"""
    task_id: UUID
    status: str
    review_type: str
    pull_request: dict
    triggered_by: str
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    duration_seconds: Optional[int] = None
    result: Optional[dict] = None
    error_message: Optional[str] = None


class TaskListResponse(BaseModel):
    """任务列表响应"""
    total: int
    tasks: List[TaskStatusResponse]
    page: int
    page_size: int


# ========== 审查端点 ==========
@router.post("/review/start", response_model=ReviewResponse)
async def start_review(
    request: ReviewRequest,
    current_user: Optional[dict] = Depends(get_current_user_optional),
):
    """
    手动触发审查任务

    支持的审查类型:
    - review: 代码审查
    - describe: 生成 MR 描述
    - improve: 代码改进建议
    - question: 问答 (需要提供 question 参数)
    """
    logger.info(
        f"Manual review requested: project={request.project_id}, "
        f"mr={request.mr_iid}, type={request.review_type}"
    )

    try:
        # 验证项目存在
        try:
            project = GitLabProject.objects.get(project_id=request.project_id)
        except GitLabProject.DoesNotExist:
            raise HTTPException(
                status_code=404,
                detail=f"Project {request.project_id} not found"
            )

        # 使用 Celery 异步触发审查
        task_id = app.send_task(
            "integration.tasks.jobs.webhook.trigger_review",
            args=[
                request.project_id,
                request.mr_iid,
                request.review_type,
                "manual",
                request.options or {},
            ],
        )

        logger.info(f"Review task {task_id} queued for {request.project_id}/{request.mr_iid}")

        return ReviewResponse(
            task_id=task_id,
            status="queued",
            review_type=request.review_type,
            message="Review task queued for processing",
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error starting review: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to start review: {str(e)}",
        )


@router.get("/review/task/{task_id}", response_model=TaskStatusResponse)
async def get_task_status(
    task_id: UUID,
    current_user: Optional[dict] = Depends(get_current_user_optional),
):
    """获取审查任务状态"""
    # TODO: 实现任务状态查询
    raise HTTPException(status_code=501, detail="Not implemented yet")


@router.get("/review/tasks", response_model=TaskListResponse)
async def list_tasks(
    project_id: Optional[int] = None,
    mr_iid: Optional[int] = None,
    status: Optional[str] = None,
    review_type: Optional[str] = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: Optional[dict] = Depends(get_current_user_optional),
):
    """获取任务列表"""
    # TODO: 实现任务列表查询
    raise HTTPException(status_code=501, detail="Not implemented yet")


@router.post("/review/task/{task_id}/cancel")
async def cancel_task(
    task_id: UUID,
    current_user: Optional[dict] = Depends(get_current_user_optional),
):
    """取消审查任务"""
    # TODO: 实现任务取消
    raise HTTPException(status_code=501, detail="Not implemented yet")


@router.get("/review/project/{project_id}/stats")
async def get_project_stats(
    project_id: int,
    current_user: Optional[dict] = Depends(get_current_user_optional),
):
    """获取项目审查统计"""
    # TODO: 实现统计查询
    raise HTTPException(status_code=501, detail="Not implemented yet")


# ========== 项目管理端点 ==========
@router.get("/projects")
async def list_projects(
    current_user: Optional[dict] = Depends(get_current_user_optional),
):
    """获取项目列表"""
    # TODO: 实现项目列表查询
    raise HTTPException(status_code=501, detail="Not implemented yet")


@router.get("/projects/{project_id}")
async def get_project(
    project_id: int,
    current_user: Optional[dict] = Depends(get_current_user_optional),
):
    """获取项目详情"""
    # TODO: 实现项目详情查询
    raise HTTPException(status_code=501, detail="Not implemented yet")


@router.post("/projects/sync")
async def sync_projects(
    current_user: Optional[dict] = Depends(get_current_user_optional),
):
    """同步 GitLab 项目"""
    try:
        # 使用 Celery 异步触发项目同步
        app.send_task("integration.tasks.jobs.sync.sync_active_projects_task")

        return {
            "status": "accepted",
            "message": "Project sync task queued",
        }

    except Exception as e:
        logger.error(f"Error syncing projects: {e}", exc_info=True)
        raise HTTPException(
            status_code=500,
            detail=f"Failed to sync projects: {str(e)}",
        )


# ========== MR 管理端点 ==========
@router.get("/projects/{project_id}/merge-requests")
async def list_merge_requests(
    project_id: int,
    state: Optional[str] = Query(None),
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    current_user: Optional[dict] = Depends(get_current_user_optional),
):
    """获取 MR 列表"""
    # TODO: 实现 MR 列表查询
    raise HTTPException(status_code=501, detail="Not implemented yet")


@router.get("/projects/{project_id}/merge-requests/{mr_iid}")
async def get_merge_request(
    project_id: int,
    mr_iid: int,
    current_user: Optional[dict] = Depends(get_current_user_optional),
):
    """获取 MR 详情"""
    # TODO: 实现 MR 详情查询
    raise HTTPException(status_code=501, detail="Not implemented yet")
