"""GitLab 数据同步服务"""
import logging
from typing import List, Optional
from django.utils import timezone
from django.db import transaction
from core.models import (
    GitLabProject,
    GitLabUser,
    PullRequest,
    ReviewConfiguration,
)
from integration.gitlab.client import GitLabClient, GitLabProject as GLProject, GitLabMR as GLMR, GitLabUser as GLUser

logger = logging.getLogger(__name__)


class ProjectSyncService:
    """项目同步服务"""

    def __init__(self, access_token: Optional[str] = None):
        self.client = GitLabClient(access_token)

    def sync_project(self, project_id: int) -> Optional[GitLabProject]:
        """
        同步单个项目

        Args:
            project_id: GitLab 项目 ID

        Returns:
            同步后的项目对象
        """
        try:
            gl_project = self.client.get_project(project_id)
            if not gl_project:
                logger.error(f"Project {project_id} not found")
                return None

            project, created = GitLabProject.objects.update_or_create(
                project_id=gl_project.id,
                defaults={
                    "name": gl_project.name,
                    "path_with_namespace": gl_project.path_with_namespace,
                    "url": gl_project.web_url,
                    "visibility": gl_project.visibility,
                    "default_branch": gl_project.default_branch,
                    "last_sync_at": timezone.now(),
                },
            )

            if created:
                logger.info(f"Created new project: {gl_project.path_with_namespace}")
                # 为新项目创建默认配置
                ReviewConfiguration.objects.get_or_create(project=project)
            else:
                logger.info(f"Updated project: {gl_project.path_with_namespace}")

            return project

        except Exception as e:
            logger.error(f"Failed to sync project {project_id}: {e}")
            return None

    def sync_project_by_path(self, path: str) -> Optional[GitLabProject]:
        """
        通过路径同步项目

        Args:
            path: 项目路径 (如: group/project)

        Returns:
            同步后的项目对象
        """
        try:
            gl_project = self.client.get_project_by_path(path)
            if not gl_project:
                logger.error(f"Project {path} not found")
                return None

            return self.sync_project(gl_project.id)

        except Exception as e:
            logger.error(f"Failed to sync project {path}: {e}")
            return None

    def sync_project_mrs(self, project: GitLabProject, limit: int = 50) -> int:
        """
        同步项目的 MR 列表

        Args:
            project: 项目对象
            limit: 同步数量限制

        Returns:
            同步的 MR 数量
        """
        try:
            gl_mrs = self.client.list_mrs(
                project.project_id,
                state="all",
                per_page=limit,
            )

            count = 0
            for gl_mr in gl_mrs:
                if self._sync_mr(project, gl_mr):
                    count += 1

            logger.info(f"Synced {count} MRs for project {project.path_with_namespace}")
            return count

        except Exception as e:
            logger.error(f"Failed to sync MRs for project {project.path_with_namespace}: {e}")
            return 0

    def sync_mr(self, project: GitLabProject, mr_iid: int) -> Optional[PullRequest]:
        """
        同步单个 MR

        Args:
            project: 项目对象
            mr_iid: MR IID

        Returns:
            同步后的 MR 对象
        """
        try:
            gl_mr = self.client.get_mr(project.project_id, mr_iid)
            if not gl_mr:
                logger.error(f"MR {project.project_id}/{mr_iid} not found")
                return None

            return self._sync_mr(project, gl_mr)

        except Exception as e:
            logger.error(f"Failed to sync MR {project.project_id}/{mr_iid}: {e}")
            return None

    def _sync_mr(self, project: GitLabProject, gl_mr: GLMR) -> Optional[PullRequest]:
        """内部方法：同步 MR"""
        try:
            # 同步作者信息
            author = self._sync_user(gl_mr.author_id, gl_mr.author_username)

            # 同步 MR
            mr, created = PullRequest.objects.update_or_create(
                project=project,
                mr_iid=gl_mr.iid,
                defaults={
                    "title": gl_mr.title,
                    "description": gl_mr.description,
                    "state": gl_mr.state,
                    "draft": gl_mr.draft,
                    "source_branch": gl_mr.source_branch,
                    "target_branch": gl_mr.target_branch,
                    "author": author,
                    "url": gl_mr.web_url,
                    "gitlab_created_at": gl_mr.created_at,
                    "gitlab_updated_at": gl_mr.updated_at,
                    "commits_count": gl_mr.commits_count,
                    "changes_count": gl_mr.changes_count,
                    "additions": gl_mr.additions,
                    "deletions": gl_mr.deletions,
                },
            )

            if created:
                logger.info(f"Created new MR: {project.path_with_namespace}!{gl_mr.iid}")
            else:
                logger.info(f"Updated MR: {project.path_with_namespace}!{gl_mr.iid}")

            return mr

        except Exception as e:
            logger.error(f"Failed to sync MR {gl_mr.iid}: {e}")
            return None

    def _sync_user(self, user_id: int, username: str) -> GitLabUser:
        """内部方法：同步用户"""
        user, created = GitLabUser.objects.get_or_create(
            gitlab_id=user_id,
            defaults={
                "gitlab_username": username,
            },
        )

        if created and username:
            # 尝试获取更完整的用户信息
            try:
                gl_user = self.client.get_user(user_id)
                if gl_user:
                    user.name = gl_user.name
                    user.email = gl_user.email
                    user.save()
            except Exception:
                pass

        return user

    @transaction.atomic
    def full_sync(self, project_id: int) -> bool:
        """
        完整同步：项目 + MR

        Args:
            project_id: GitLab 项目 ID

        Returns:
            是否成功
        """
        try:
            # 同步项目
            project = self.sync_project(project_id)
            if not project:
                return False

            # 同步 MR
            self.sync_project_mrs(project)

            return True

        except Exception as e:
            logger.error(f"Failed to perform full sync for project {project_id}: {e}")
            return False


class WebhookSyncService:
    """Webhook 触发的快速同步服务"""

    def __init__(self, access_token: Optional[str] = None):
        self.client = GitLabClient(access_token)

    def sync_mr_from_webhook(self, project_path: str, mr_iid: int) -> Optional[PullRequest]:
        """
        从 Webhook 事件同步 MR

        Args:
            project_path: 项目路径
            mr_iid: MR IID

        Returns:
            同步后的 MR 对象
        """
        try:
            # 获取项目
            gl_project = self.client.get_project_by_path(project_path)
            if not gl_project:
                return None

            # 获取或创建项目
            project, _ = GitLabProject.objects.get_or_create(
                project_id=gl_project.id,
                defaults={
                    "name": gl_project.name,
                    "path_with_namespace": gl_project.path_with_namespace,
                    "url": gl_project.web_url,
                    "visibility": gl_project.visibility,
                    "default_branch": gl_project.default_branch,
                },
            )

            # 获取 MR
            gl_mr = self.client.get_mr(gl_project.id, mr_iid)
            if not gl_mr:
                return None

            # 同步
            sync_service = ProjectSyncService()
            return sync_service._sync_mr(project, gl_mr)

        except Exception as e:
            logger.error(f"Failed to sync MR from webhook: {e}")
            return None
