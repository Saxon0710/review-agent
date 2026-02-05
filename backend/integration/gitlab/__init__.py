"""GitLab Integration Module"""
from .client import GitLabClient, GitLabMR, GitLabProject as GLProject, GitLabUser as GLUser
from .webhook import WebhookProcessor, WebhookEvent, webhook_processor
from .sync import ProjectSyncService, WebhookSyncService

__all__ = [
    "GitLabClient",
    "GitLabMR",
    "GLProject",
    "GLUser",
    "WebhookProcessor",
    "WebhookEvent",
    "webhook_processor",
    "ProjectSyncService",
    "WebhookSyncService",
]
