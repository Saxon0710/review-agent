"""
PR 描述生成工具
"""
import logging
from typing import Dict, Any
from review.tools.base import BaseReviewTool

logger = logging.getLogger(__name__)


class DescriberTool(BaseReviewTool):
    """PR 描述生成工具"""

    async def run(self, **kwargs) -> Dict[str, Any]:
        """执行描述生成"""
        logger.info(f"Starting description generation for {self.pr_url}")

        pr_info = self.get_pr_info()

        # 构建参数
        ai_params = {
            **pr_info,
            "files": self.get_files_list(),
            "diff": self.get_diff_content(max_tokens=self.ai_handler.max_tokens),
        }

        # 调用 AI
        response = await self.call_ai("describe", **ai_params)

        # 发布结果
        await self._publish_description(response)

        return {
            "success": True,
            "description": response,
        }

    async def _publish_description(self, description: str):
        """发布描述到 GitLab"""
        if config.ai.get("publish_output", True):
            self.provider.publish_persistent_comment(
                description,
                initial_header="## 📝 AI 生成的 PR 描述",
            )
