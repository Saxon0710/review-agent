"""
问答工具
"""
import logging
from typing import Dict, Any
from review.tools.base import BaseReviewTool

logger = logging.getLogger(__name__)


class QuestionerTool(BaseReviewTool):
    """问答工具"""

    async def run(self, question: str, **kwargs) -> Dict[str, Any]:
        """执行问答"""
        logger.info(f"Processing question for {self.pr_url}")

        pr_info = self.get_pr_info()

        # 构建参数
        ai_params = {
            **pr_info,
            "question": question,
            "diff": self.get_diff_content(max_tokens=self.ai_handler.max_tokens),
        }

        # 调用 AI
        response = await self.call_ai("question", **ai_params)

        # 发布回答
        await self._publish_answer(response)

        return {
            "success": True,
            "answer": response,
        }

    async def _publish_answer(self, answer: str):
        """发布回答到 GitLab"""
        if config.ai.get("publish_output", True):
            self.provider.publish_comment(answer, is_temporary=True)
