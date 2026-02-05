"""
代码改进建议工具
"""
import logging
from typing import Dict, Any
import yaml
from review.tools.base import BaseReviewTool

logger = logging.getLogger(__name__)


class ImproverTool(BaseReviewTool):
    """代码改进建议工具"""

    async def run(self, **kwargs) -> Dict[str, Any]:
        """执行代码改进分析"""
        logger.info(f"Starting improve analysis for {self.pr_url}")

        pr_info = self.get_pr_info()

        # 获取需要改进的代码
        code_content = kwargs.get("code", self.get_diff_content())

        # 构建参数
        ai_params = {
            **pr_info,
            "code": code_content,
            "extra_instructions": self.project_config.get("review_extra_instructions", ""),
        }

        # 调用 AI
        response = await self.call_ai("improve", **ai_params)

        # 解析结果
        result = self._parse_response(response)

        # 发布结果
        await self._publish_improvements(result)

        return {
            "success": True,
            "result": result,
        }

    def _parse_response(self, response: str) -> Dict[str, Any]:
        """解析 AI 响应"""
        # 简化实现：直接返回原始响应
        return {"raw_response": response}

    async def _publish_improvements(self, result: Dict[str, Any]):
        """发布改进建议"""
        output = self._format_output(result)

        if config.ai.get("publish_output", True):
            self.provider.publish_persistent_comment(
                output,
                initial_header="## 💡 代码改进建议",
            )

    def _format_output(self, result: Dict[str, Any]) -> str:
        """格式化输出"""
        return result.get("raw_response", "")
