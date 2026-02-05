"""集成模块"""
from .gitlab import GitLabClient, WebhookProcessor, ProjectSyncService

__all__ = [
    "GitLabClient",
    "WebhookProcessor",
    "ProjectSyncService",
]
