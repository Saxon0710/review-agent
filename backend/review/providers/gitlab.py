"""
GitLab Provider 实现
基于 PR-Agent 的 GitLabProvider 和 python-gitlab 库
"""
import gitlab
from typing import List, Dict, Any, Optional
import logging

from .base import GitProvider, FilePatchInfo, PRInfo
from config.settings import config

logger = logging.getLogger(__name__)


class GitLabProvider(GitProvider):
    """GitLab Provider 实现"""

    def __init__(self, pr_url: str, access_token: str = None):
        super().__init__(pr_url)

        # 解析 MR URL
        # 格式: https://gitlab.com/group/project/-/merge_requests/123
        parts = pr_url.strip("/").split("/-/")
        project_path = parts[-2].replace("/", "/")
        mr_iid = int(parts[-1])

        self.project_path = project_path
        self.mr_iid = mr_iid

        # 初始化 GitLab 客户端
        self.gl = gitlab.Gitlab(
            url=config.gitlab["url"],
            private_token=access_token or config.gitlab["personal_access_token"],
            ssl_verify=config.gitlab["ssl_verify"],
        )

        # 超时配置
        self.gl.timeout = config.gitlab["timeout"]

        # 缓存项目对象
        self._project = None
        self._merge_request = None

    @property
    def project(self):
        """获取 GitLab 项目对象"""
        if self._project is None:
            self._project = self.gl.projects.get(self.project_path)
        return self._project

    @property
    def merge_request(self):
        """获取 GitLab MR 对象"""
        if self._merge_request is None:
            self._merge_request = self.project.mergerequests.get(self.mr_iid)
        return self._merge_request

    def get_pr_info(self) -> PRInfo:
        """获取 PR 基本信息"""
        if self._pr_info:
            return self._pr_info

        mr = self.merge_request

        self._pr_info = PRInfo(
            pr_url=self.pr_url,
            pr_id=mr.id,
            pr_iid=mr.iid,
            title=mr.title,
            description=mr.description or "",
            source_branch=mr.source_branch,
            target_branch=mr.target_branch,
            state=mr.state,
            author=mr.author["username"] if mr.author else "unknown",
            is_draft=mr.work_in_progress,
            url=mr.web_url,
            diff_url=f"{mr.web_url}/diffs",
            created_at=mr.created_at,
            updated_at=mr.updated_at,
        )

        return self._pr_info

    def get_diff_files(self) -> List[FilePatchInfo]:
        """获取文件差异"""
        if self._diff_files:
            return self._diff_files

        self._diff_files = []
        changes = self.merge_request.changes()

        for change in changes:
            # 获取 diff 内容
            diff = change.get("diff", "")

            self._diff_files.append(FilePatchInfo(
                filename=change["new_path"] if change["action"] != "deleted" else change["old_path"],
                old_filename=change["old_path"] if change["old_path"] != change["new_path"] else None,
                patch=diff,
                edit_type=change["action"].upper(),  # added, deleted, modified, renamed
                num_plus_lines=change.get("additions", 0),
                num_minus_lines=change.get("deletions", 0),
            ))

        return self._diff_files

    def get_files(self) -> List[str]:
        """获取变更文件列表"""
        diff_files = self.get_diff_files()
        return [f.filename for f in diff_files]

    def publish_comment(self, comment: str, is_temporary: bool = False) -> None:
        """发布评论"""
        if is_temporary:
            self.merge_request.notes.create({"body": comment})
        else:
            self.merge_request.discussions.create({
                "body": comment,
                "position": None,  # 整体评论
            })

    def publish_inline_comment(
        self,
        comment: str,
        file_path: str,
        line_start: int,
        line_end: int,
        side: str = "RIGHT"
    ) -> None:
        """发布行内评论"""
        # 需要找到正确的位置信息
        # GitLab API 需要 position_hash 或 position 对象
        self.merge_request.discussions.create({
            "body": comment,
            "position": {
                "base_sha": self.merge_request.diff_refs.base_sha,
                "start_sha": self.merge_request.diff_refs.start_sha,
                "head_sha": self.merge_request.diff_refs.head_sha,
                "position_type": "text",
                "new_path": file_path,
                "new_line": line_end if side == "RIGHT" else None,
                "old_line": line_start if side == "LEFT" else None,
            }
        })

    def publish_persistent_comment(
        self,
        comment: str,
        initial_header: str = "",
        update_header: bool = True
    ) -> None:
        """发布持久化评论"""
        # 先查找是否有之前的持久化评论
        notes = self.merge_request.notes.list()
        bot_notes = [n for n in notes if self._is_bot_comment(n)]

        if bot_notes and update_header:
            # 更新现有评论
            latest_note = bot_notes[0]
            latest_note.body = f"{initial_header}\n\n{comment}"
            latest_note.save()
        else:
            # 创建新评论
            body = f"{initial_header}\n\n{comment}" if initial_header else comment
            self.merge_request.notes.create({"body": body})

    def get_pr_description(self) -> str:
        """获取 PR 描述"""
        pr_info = self.get_pr_info()
        return f"{pr_info.title}\n\n{pr_info.description}"

    def get_commit_messages(self) -> str:
        """获取提交信息"""
        commits = self.merge_request.commits()
        commit_msgs = []
        for commit in commits:
            commit_msgs.append(f"- {commit.title} ({commit.short_id})")
        return "\n".join(commit_msgs)

    def get_languages(self) -> List[str]:
        """获取使用的编程语言"""
        # 简单实现：通过文件扩展名推断
        languages = set()
        for f in self.get_diff_files():
            lang = self._infer_language(f.filename)
            if lang:
                languages.add(lang)
        return list(languages)

    def get_issue_comments(self) -> List[Dict]:
        """获取评论列表"""
        notes = self.merge_request.notes.list()
        return [
            {
                "id": n.id,
                "author": n.author["username"] if n.author else "unknown",
                "body": n.body,
                "created_at": n.created_at,
                "system": n.system,
            }
            for n in notes
        ]

    def remove_comment(self, comment_id: int) -> None:
        """删除评论"""
        note = self.merge_request.notes.get(comment_id)
        note.delete()

    def publish_labels(self, labels: List[str]) -> None:
        """添加标签"""
        self.merge_request.labels = labels
        self.merge_request.save()

    def get_pr_labels(self) -> List[str]:
        """获取标签"""
        mr = self.merge_request
        return mr.labels

    def _is_bot_comment(self, note) -> bool:
        """判断是否是机器人评论"""
        # 检查是否有持久化评论标记
        body = note.body or ""
        return "<!-- review-agent-persistent -->" in body or "Review Agent" in body

    def _infer_language(self, filename: str) -> Optional[str]:
        """从文件名推断编程语言"""
        from core.constants import LANGUAGE_EXTENSIONS

        for lang, extensions in LANGUAGE_EXTENSIONS.items():
            for ext in extensions:
                if filename.endswith(ext):
                    return lang
        return None
