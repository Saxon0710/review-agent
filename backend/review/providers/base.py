"""
Git Provider 抽象基类
基于 PR-Agent 的 GitProvider 设计
"""
from abc import ABC, abstractmethod
from typing import List, Dict, Any, Optional
from dataclasses import dataclass


@dataclass
class FilePatchInfo:
    """文件差异信息"""
    filename: str
    old_filename: Optional[str] = None
    patch: str = ""
    base_file: str = ""
    head_file: str = ""
    tokens: int = 0
    num_plus_lines: int = 0
    num_minus_lines: int = 0
    edit_type: str = "MODIFIED"  # ADDED, DELETED, MODIFIED, RENAMED
    language: Optional[str] = None
    ai_file_summary: str = ""


@dataclass
class PRInfo:
    """PR 基本信息"""
    pr_url: str
    pr_id: int
    pr_iid: int
    title: str
    description: str
    source_branch: str
    target_branch: str
    state: str
    author: str
    is_draft: bool
    url: str
    diff_url: str
    created_at: str
    updated_at: str


class GitProvider(ABC):
    """Git Provider 抽象基类"""

    def __init__(self, pr_url: str):
        self.pr_url = pr_url
        self._pr_info: Optional[PRInfo] = None
        self._diff_files: Optional[List[FilePatchInfo]] = None

    @abstractmethod
    def get_pr_info(self) -> PRInfo:
        """获取 PR 基本信息"""
        pass

    @abstractmethod
    def get_diff_files(self) -> List[FilePatchInfo]:
        """获取文件差异"""
        pass

    @abstractmethod
    def get_files(self) -> List[str]:
        """获取变更文件列表"""
        pass

    @abstractmethod
    def publish_comment(self, comment: str, is_temporary: bool = False) -> None:
        """发布评论"""
        pass

    @abstractmethod
    def publish_inline_comment(
        self,
        comment: str,
        file_path: str,
        line_start: int,
        line_end: int,
        side: str = "RIGHT"
    ) -> None:
        """发布行内评论"""
        pass

    @abstractmethod
    def publish_persistent_comment(
        self,
        comment: str,
        initial_header: str = "",
        update_header: bool = True
    ) -> None:
        """发布持久化评论（可更新）"""
        pass

    @abstractmethod
    def get_pr_description(self) -> str:
        """获取 PR 描述"""
        pass

    @abstractmethod
    def get_commit_messages(self) -> str:
        """获取提交信息"""
        pass

    @abstractmethod
    def get_languages(self) -> List[str]:
        """获取使用的编程语言"""
        pass

    @abstractmethod
    def get_issue_comments(self) -> List[Dict]:
        """获取评论列表"""
        pass

    @abstractmethod
    def remove_comment(self, comment_id: int) -> None:
        """删除评论"""
        pass

    @abstractmethod
    def publish_labels(self, labels: List[str]) -> None:
        """添加标签"""
        pass

    @abstractmethod
    def get_pr_labels(self) -> List[str]:
        """获取标签"""
        pass

    def is_supported(self, capability: str) -> bool:
        """检查是否支持某个功能"""
        return capability in self.get_capabilities()

    def get_capabilities(self) -> List[str]:
        """获取支持的功能列表"""
        return [
            "diff_files",
            "publish_comment",
            "publish_inline_comment",
            "publish_persistent_comment",
            "get_pr_description",
            "get_commit_messages",
            "get_languages",
            "get_issue_comments",
            "remove_comment",
            "publish_labels",
        ]
