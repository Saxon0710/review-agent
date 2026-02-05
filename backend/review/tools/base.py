"""
审查工具基类
"""
import logging
from typing import Dict, Any, Optional
from abc import ABC, abstractmethod

from review.ai.litellm import LiteLLMHandler
from review.ai.manager import prompt_manager
from review.providers.gitlab import GitLabProvider
from config.settings import config

logger = logging.getLogger(__name__)


class BaseReviewTool(ABC):
    """审查工具基类"""

    def __init__(self, pr_url: str, access_token: str, project_config: dict = None):
        self.pr_url = pr_url
        self.project_config = project_config or {}

        # 初始化 GitLab Provider
        self.provider = GitLabProvider(pr_url, access_token)

        # 初始化 AI Handler
        self.ai_handler = LiteLLMHandler(project_config)

        logger.info(f"Initialized {self.__class__.__name__} for {pr_url}")

    @abstractmethod
    async def run(self, **kwargs) -> Dict[str, Any]:
        """执行审查"""
        pass

    def get_pr_info(self) -> Dict[str, Any]:
        """获取 PR 信息"""
        pr_info = self.provider.get_pr_info()
        return {
            "project_path": self.provider.project_path,
            "mr_iid": self.provider.mr_iid,
            "title": pr_info.title,
            "description": pr_info.description,
            "source_branch": pr_info.source_branch,
            "target_branch": pr_info.target_branch,
            "state": pr_info.state,
            "author": pr_info.author,
            "url": pr_info.url,
        }

    def get_diff_content(self, max_tokens: int = None) -> str:
        """获取差异内容"""
        diff_files = self.provider.get_diff_files()

        # 简单实现：直接拼接 diff
        diff_parts = []
        total_tokens = 0

        for file_info in diff_files:
            # 估算 token 数（粗略：1 token ≈ 4 字符）
            file_tokens = len(file_info.patch) // 4

            if max_tokens and total_tokens + file_tokens > max_tokens:
                break

            diff_parts.append(f"```diff\n{file_info.patch}\n```")
            total_tokens += file_tokens

        return "\n\n".join(diff_parts)

    def get_files_list(self) -> str:
        """获取文件列表"""
        diff_files = self.provider.get_diff_files()
        files = []

        for f in diff_files:
            edit_symbol = {
                "ADDED": "+",
                "DELETED": "-",
                "MODIFIED": "M",
                "RENAMED": "R",
            }.get(f.edit_type, "M")

            files.append(f"{edit_symbol} {f.filename}")

        return "\n".join(files)

    def get_commit_messages(self) -> str:
        """获取提交信息"""
        return self.provider.get_commit_messages()

    async def call_ai(self, review_type: str, **kwargs) -> str:
        """调用 AI"""
        # 渲染 Prompt
        system_prompt, user_prompt = prompt_manager.render(
            review_type,
            **kwargs
        )

        logger.info(f"Calling AI for {review_type}")

        # 调用 AI
        response, finish_reason = await self.ai_handler.chat_completion(
            system=system_prompt,
            user=user_prompt,
        )

        logger.info(f"AI response received: finish_reason={finish_reason}")

        return response
