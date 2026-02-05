"""审查任务"""
import logging
import uuid
from typing import Optional, Dict, Any
from django.utils import timezone
from django.db import transaction
from core.models import (
    GitLabProject,
    PullRequest,
    ReviewTask,
    ReviewConfiguration,
    ReviewComment,
)
from integration.gitlab.client import GitLabClient
from integration.gitlab.sync import ProjectSyncService
from integration.tasks.celery import app
from review.providers.gitlab import GitLabProvider
from review.tools.reviewer import ReviewerTool
from review.tools.describer import DescriberTool
from review.tools.improver import ImproverTool
from review.tools.questioner import QuestionerTool

logger = logging.getLogger(__name__)


class ReviewTaskRunner:
    """审查任务执行器"""

    def __init__(self, access_token: Optional[str] = None):
        self.client = GitLabClient(access_token)
        self.sync_service = ProjectSyncService(access_token)

    def run_review(
        self,
        project_path: str,
        mr_iid: int,
        review_type: str = "review",
        triggered_by: str = "webhook",
        question: Optional[str] = None,
        config_override: Optional[Dict[str, Any]] = None,
    ) -> ReviewTask:
        """
        运行审查任务

        Args:
            project_path: 项目路径
            mr_iid: MR IID
            review_type: 审查类型
            triggered_by: 触发方式
            question: 问题 (仅用于 question 类型)
            config_override: 配置覆盖

        Returns:
            ReviewTask 对象
        """
        # 获取项目
        project = GitLabProject.objects.get(path_with_namespace=project_path)

        # 获取配置
        config = ReviewConfiguration.objects.get(project=project)

        # 创建任务
        task = ReviewTask.objects.create(
            task_id=uuid.uuid4(),
            pull_request=PullRequest.objects.get(
                project=project,
                mr_iid=mr_iid,
            ),
            review_type=review_type,
            status="running",
            triggered_by=triggered_by,
            ai_model=config.ai_model,
            config=config_override or config.settings,
        )

        # 执行审查
        try:
            result = self._execute_review(task, question)

            task.status = "completed"
            task.result = result
            task.completed_at = timezone.now()
            task.save()

            logger.info(f"Review task {task.task_id} completed successfully")

        except Exception as e:
            logger.error(f"Review task {task.task_id} failed: {e}")
            task.status = "failed"
            task.error_message = str(e)
            task.completed_at = timezone.now()
            task.save()

        return task

    def _execute_review(self, task: ReviewTask, question: Optional[str] = None) -> Dict[str, Any]:
        """执行审查逻辑"""
        pr = task.pull_request
        pr_url = pr.url

        # 获取项目配置
        config = ReviewConfiguration.objects.get(project=pr.project)

        # 创建 Provider
        provider = GitLabProvider(
            pr_url=pr_url,
            access_token=self.client.gl.private_token,
        )

        # AI 配置
        ai_config = {
            "model": config.ai_model,
            "temperature": config.ai_temperature,
        }

        # 根据类型执行不同的审查
        if task.review_type == "review":
            tool = ReviewerTool(provider, ai_config)
            result = tool.run()

        elif task.review_type == "describe":
            tool = DescriberTool(provider, ai_config)
            result = tool.run()

        elif task.review_type == "improve":
            tool = ImproverTool(provider, ai_config)
            result = tool.run()

        elif task.review_type == "question":
            tool = QuestionerTool(provider, ai_config)
            result = tool.run(question)

        else:
            raise ValueError(f"Unknown review type: {task.review_type}")

        # 保存评论
        if result.get("comments"):
            for comment_data in result["comments"]:
                ReviewComment.objects.create(
                    review_task=task,
                    file_path=comment_data.get("file_path", ""),
                    line_number=comment_data.get("line_number"),
                    body=comment_data.get("body", ""),
                )

        return result


@transaction.atomic
def create_review_task(
    project_path: str,
    mr_iid: int,
    review_type: str = "review",
    triggered_by: str = "webhook",
    question: Optional[str] = None,
) -> Optional[ReviewTask]:
    """
    创建审查任务

    Args:
        project_path: 项目路径
        mr_iid: MR IID
        review_type: 审查类型
        triggered_by: 触发方式
        question: 问题

    Returns:
        创建的任务对象
    """
    try:
        # 获取项目
        project = GitLabProject.objects.get(path_with_namespace=project_path)

        # 获取或创建 MR
        mr, _ = PullRequest.objects.get_or_create(
            project=project,
            mr_iid=mr_iid,
            defaults={
                "title": f"MR {mr_iid}",
                "state": "opened",
                "draft": False,
                "source_branch": "",
                "target_branch": "",
            },
        )

        # 获取配置
        config = ReviewConfiguration.objects.get(project=project)

        # 创建任务
        task = ReviewTask.objects.create(
            task_id=uuid.uuid4(),
            pull_request=mr,
            review_type=review_type,
            status="pending",
            triggered_by=triggered_by,
            ai_model=config.ai_model,
            config=config.settings,
        )

        logger.info(
            f"Created review task {task.task_id} for {project_path}!{mr_iid} "
            f"(type: {review_type})"
        )

        return task

    except Exception as e:
        logger.error(f"Failed to create review task: {e}")
        return None


# ========== Celery 任务包装器 ==========


@app.task(name="integration.tasks.jobs.review.execute_review", bind=True, max_retries=3)
def execute_review(self, task_id: str) -> Dict[str, Any]:
    """
    执行审查任务的 Celery 包装器

    Args:
        self: Celery task 实例
        task_id: 任务 ID

    Returns:
        执行结果
    """
    try:
        # 获取任务
        task = ReviewTask.objects.get(task_id=task_id)

        # 更新状态
        task.status = "running"
        task.started_at = timezone.now()
        task.save()

        # 执行审查
        runner = ReviewTaskRunner()
        result_task = runner.run_review(
            project_path=task.pull_request.project.path_with_namespace,
            mr_iid=task.pull_request.mr_iid,
            review_type=task.review_type,
            triggered_by=task.triggered_by,
            question=task.options.get("question"),
            config_override=task.options,
        )

        # 刷新并返回
        result_task.refresh_from_db()

        return {
            "task_id": str(result_task.task_id),
            "status": result_task.status,
            "review_type": result_task.review_type,
            "result": result_task.result,
        }

    except ReviewTask.DoesNotExist:
        logger.error(f"Review task {task_id} not found")
        return {"status": "error", "message": "Task not found"}

    except Exception as e:
        logger.error(f"Review task {task_id} failed: {e}", exc_info=True)

        # 更新任务状态
        try:
            task = ReviewTask.objects.get(task_id=task_id)
            task.status = "failed"
            task.error_message = str(e)
            task.completed_at = timezone.now()
            task.save()
        except ReviewTask.DoesNotExist:
            pass

        # 重试逻辑
        if self.request.retries < self.max_retries:
            raise self.retry(exc=e, countdown=60 * (self.request.retries + 1))

        return {"status": "error", "message": str(e)}


@app.task(name="integration.tasks.jobs.review.execute_review_sync")
def execute_review_sync(
    project_id: int,
    mr_iid: int,
    review_type: str = "review",
    triggered_by: str = "manual",
    question: Optional[str] = None,
) -> Dict[str, Any]:
    """
    同步执行审查任务（用于手动触发）

    Args:
        project_id: 项目 ID
        mr_iid: MR IID
        review_type: 审查类型
        triggered_by: 触发方式
        question: 问题

    Returns:
        执行结果
    """
    try:
        # 获取项目
        project = GitLabProject.objects.get(project_id=project_id)

        # 创建任务
        task = create_review_task(
            project_path=project.path_with_namespace,
            mr_iid=mr_iid,
            review_type=review_type,
            triggered_by=triggered_by,
        )

        if not task:
            return {"status": "error", "message": "Failed to create task"}

        # 执行审查
        runner = ReviewTaskRunner()
        result_task = runner.run_review(
            project_path=project.path_with_namespace,
            mr_iid=mr_iid,
            review_type=review_type,
            triggered_by=triggered_by,
            question=question,
        )

        return {
            "task_id": str(result_task.task_id),
            "status": result_task.status,
            "review_type": result_task.review_type,
            "result": result_task.result,
        }

    except Exception as e:
        logger.error(f"Sync review failed: {e}", exc_info=True)
        return {"status": "error", "message": str(e)}
