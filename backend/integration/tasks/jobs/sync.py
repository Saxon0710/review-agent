"""同步任务"""
import logging
from django.utils import timezone
from core.models import GitLabProject
from integration.gitlab.sync import ProjectSyncService
from integration.tasks.celery import app

logger = logging.getLogger(__name__)


def sync_active_projects(limit: int = 10) -> int:
    """
    同步活跃项目

    Args:
        limit: 最多同步的项目数量

    Returns:
        同步的项目数量
    """
    active_projects = GitLabProject.objects.filter(
        is_active=True,
    ).order_by("-last_sync_at")[:limit]

    count = 0
    sync_service = ProjectSyncService()

    for project in active_projects:
        try:
            sync_service.full_sync(project.project_id)
            count += 1
        except Exception as e:
            logger.error(f"Failed to sync project {project.path_with_namespace}: {e}")

    logger.info(f"Synced {count}/{len(active_projects)} active projects")
    return count


def sync_project(project_id: int) -> bool:
    """
    同步单个项目

    Args:
        project_id: 项目 ID

    Returns:
        是否成功
    """
    sync_service = ProjectSyncService()
    return sync_service.full_sync(project_id)


def cleanup_old_tasks(days: int = 30) -> int:
    """
    清理旧任务

    Args:
        days: 保留天数

    Returns:
        删除的任务数量
    """
    from core.models import ReviewTask

    cutoff = timezone.now() - timezone.timedelta(days=days)
    count, _ = ReviewTask.objects.filter(
        created_at__lt=cutoff,
        status__in=["completed", "failed", "cancelled"],
    ).delete()

    logger.info(f"Cleaned up {count} old tasks (older than {days} days)")
    return count


# ========== Celery 任务包装器 ==========


@app.task(name="integration.tasks.jobs.sync.sync_active_projects_task")
def sync_active_projects_task(limit: int = 10) -> int:
    """
    同步活跃项目的 Celery 任务

    Args:
        limit: 最多同步的项目数量

    Returns:
        同步的项目数量
    """
    return sync_active_projects(limit)


@app.task(name="integration.tasks.jobs.sync.sync_project_task")
def sync_project_task(project_id: int) -> bool:
    """
    同步单个项目的 Celery 任务

    Args:
        project_id: 项目 ID

    Returns:
        是否成功
    """
    return sync_project(project_id)


@app.task(name="integration.tasks.jobs.sync.cleanup_old_tasks_task")
def cleanup_old_tasks_task(days: int = 30) -> int:
    """
    清理旧任务的 Celery 任务

    Args:
        days: 保留天数

    Returns:
        删除的任务数量
    """
    return cleanup_old_tasks(days)
