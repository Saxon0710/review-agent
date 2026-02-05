"""Celery 任务定义"""
from .review import ReviewTaskRunner, create_review_task, execute_review, execute_review_sync
from .sync import (
    sync_active_projects,
    sync_project,
    cleanup_old_tasks,
    sync_active_projects_task,
    sync_project_task,
    cleanup_old_tasks_task,
)
from .webhook import (
    process_merge_request_event,
    process_note_event,
    process_push_event,
    trigger_review,
)

__all__ = [
    # Review 任务
    "ReviewTaskRunner",
    "create_review_task",
    "execute_review",
    "execute_review_sync",
    # Sync 任务
    "sync_active_projects",
    "sync_project",
    "cleanup_old_tasks",
    "sync_active_projects_task",
    "sync_project_task",
    "cleanup_old_tasks_task",
    # Webhook 任务
    "process_merge_request_event",
    "process_note_event",
    "process_push_event",
    "trigger_review",
]
