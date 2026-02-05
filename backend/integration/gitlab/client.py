"""GitLab API 客户端封装"""
import logging
from typing import Optional, List, Dict, Any
from dataclasses import dataclass
import gitlab
from config.settings import settings

logger = logging.getLogger(__name__)


@dataclass
class GitLabMR:
    """GitLab MR 数据类"""
    iid: int
    project_id: int
    title: str
    description: str
    state: str
    draft: bool
    source_branch: str
    target_branch: str
    author_id: int
    author_username: str
    web_url: str
    created_at: str
    updated_at: str
    commits_count: int
    changes_count: int
    additions: int
    deletions: int


@dataclass
class GitLabProject:
    """GitLab 项目数据类"""
    id: int
    name: str
    path_with_namespace: str
    web_url: str
    visibility: str
    default_branch: str


@dataclass
class GitLabUser:
    """GitLab 用户数据类"""
    id: int
    username: str
    name: str
    email: str


class GitLabClient:
    """GitLab API 客户端"""

    def __init__(self, access_token: Optional[str] = None):
        """
        初始化 GitLab 客户端

        Args:
            access_token: GitLab 访问令牌，如果不提供则使用配置中的默认令牌
        """
        self.url = settings.get("gitlab.url", "https://gitlab.com")
        token = access_token or settings.get("gitlab.access_token")

        if not token:
            raise ValueError("GitLab access token is required")

        self.gl = gitlab.Gitlab(
            self.url,
            private_token=token,
            timeout=settings.get("gitlab.timeout", 30),
        )

    def get_project(self, project_id: int) -> Optional[GitLabProject]:
        """获取项目信息"""
        try:
            project = self.gl.projects.get(project_id)
            return GitLabProject(
                id=project.id,
                name=project.name,
                path_with_namespace=project.path_with_namespace,
                web_url=project.web_url,
                visibility=project.visibility,
                default_branch=project.default_branch or "main",
            )
        except gitlab.exceptions.GitlabError as e:
            logger.error(f"Failed to get project {project_id}: {e}")
            return None

    def get_project_by_path(self, path: str) -> Optional[GitLabProject]:
        """通过路径获取项目信息"""
        try:
            project = self.gl.projects.get(path)
            return GitLabProject(
                id=project.id,
                name=project.name,
                path_with_namespace=project.path_with_namespace,
                web_url=project.web_url,
                visibility=project.visibility,
                default_branch=project.default_branch or "main",
            )
        except gitlab.exceptions.GitlabError as e:
            logger.error(f"Failed to get project {path}: {e}")
            return None

    def get_mr(self, project_id: int, mr_iid: int) -> Optional[GitLabMR]:
        """获取 MR 信息"""
        try:
            project = self.gl.projects.get(project_id)
            mr = project.mergerequests.get(mr_iid)

            # 获取作者信息
            author = mr.author
            author_username = author.username if author else "unknown"

            # 获取变更统计
            additions = 0
            deletions = 0
            changes_count = 0

            try:
                changes = mr.changes()
                changes_count = len(changes.get("changes", []))
                for change in changes.get("changes", []):
                    diff = change.get("diff", "")
                    additions += diff.count("+") - diff.count("++") if diff else 0
                    deletions += diff.count("-") - diff.count("--") if diff else 0
            except Exception:
                pass

            return GitLabMR(
                iid=mr.iid,
                project_id=project_id,
                title=mr.title,
                description=mr.description or "",
                state=mr.state,
                draft=mr.work_in_progress,
                source_branch=mr.source_branch,
                target_branch=mr.target_branch,
                author_id=author.id if author else 0,
                author_username=author_username,
                web_url=mr.web_url,
                created_at=mr.created_at,
                updated_at=mr.updated_at,
                commits_count=mr.commits(),
                changes_count=changes_count,
                additions=additions,
                deletions=deletions,
            )
        except gitlab.exceptions.GitlabError as e:
            logger.error(f"Failed to get MR {project_id}/{mr_iid}: {e}")
            return None

    def get_mr_diff(self, project_id: int, mr_iid: int) -> Optional[Dict[str, Any]]:
        """获取 MR 的 diff 信息"""
        try:
            project = self.gl.projects.get(project_id)
            mr = project.mergerequests.get(mr_iid)
            return mr.changes()
        except gitlab.exceptions.GitlabError as e:
            logger.error(f"Failed to get MR diff {project_id}/{mr_iid}: {e}")
            return None

    def list_mrs(
        self,
        project_id: int,
        state: str = "opened",
        per_page: int = 100,
    ) -> List[GitLabMR]:
        """列出项目的 MR"""
        try:
            project = self.gl.projects.get(project_id)
            mrs = project.mergerequests.list(
                state=state,
                per_page=per_page,
                order_by="created_at",
                sort="desc",
            )

            result = []
            for mr in mrs:
                author = mr.author
                author_username = author.username if author else "unknown"

                result.append(
                    GitLabMR(
                        iid=mr.iid,
                        project_id=project_id,
                        title=mr.title,
                        description=mr.description or "",
                        state=mr.state,
                        draft=mr.work_in_progress,
                        source_branch=mr.source_branch,
                        target_branch=mr.target_branch,
                        author_id=author.id if author else 0,
                        author_username=author_username,
                        web_url=mr.web_url,
                        created_at=mr.created_at,
                        updated_at=mr.updated_at,
                        commits_count=0,  # 避免过多 API 调用
                        changes_count=0,
                        additions=0,
                        deletions=0,
                    )
                )

            return result
        except gitlab.exceptions.GitlabError as e:
            logger.error(f"Failed to list MRs for project {project_id}: {e}")
            return []

    def get_user(self, user_id: int) -> Optional[GitLabUser]:
        """获取用户信息"""
        try:
            user = self.gl.users.get(user_id)
            return GitLabUser(
                id=user.id,
                username=user.username,
                name=user.name,
                email=user.email or "",
            )
        except gitlab.exceptions.GitlabError as e:
            logger.error(f"Failed to get user {user_id}: {e}")
            return None

    def get_file_content(
        self,
        project_id: int,
        file_path: str,
        ref: str = "HEAD",
    ) -> Optional[str]:
        """获取文件内容"""
        try:
            project = self.gl.projects.get(project_id)
            file = project.files.get(file_path=file_path, ref=ref)
            return file.decode()
        except gitlab.exceptions.GitlabError as e:
            logger.error(f"Failed to get file {file_path} from {project_id}: {e}")
            return None

    def post_mr_comment(
        self,
        project_id: int,
        mr_iid: int,
        body: str,
        file_path: Optional[str] = None,
        line: Optional[int] = None,
    ) -> bool:
        """在 MR 上发布评论"""
        try:
            project = self.gl.projects.get(project_id)
            mr = project.mergerequests.get(mr_iid)

            if file_path and line is not None:
                # 行内评论
                mr.notes.create({"body": body})
            else:
                # 一般评论
                mr.notes.create({"body": body})

            return True
        except gitlab.exceptions.GitlabError as e:
            logger.error(f"Failed to post comment on {project_id}/{mr_iid}: {e}")
            return False

    def test_connection(self) -> bool:
        """测试连接"""
        try:
            self.gl.auth()
            logger.info(f"GitLab connection successful: {self.url}")
            return True
        except Exception as e:
            logger.error(f"GitLab connection failed: {e}")
            return False

    @classmethod
    def parse_mr_url(cls, url: str) -> Optional[Dict[str, Any]]:
        """
        解析 GitLab MR URL

        支持的格式:
        - https://gitlab.com/group/project/-/merge_requests/123
        - https://gitlab.example.com/group/subgroup/project/-/merge_requests/456
        """
        import re

        pattern = r"https?://([^/]+)/(.+)/-/merge_requests/(\d+)"
        match = re.match(pattern, url)

        if match:
            return {
                "url": f"https://{match.group(1)}",
                "project_path": match.group(2),
                "mr_iid": int(match.group(3)),
            }

        return None
