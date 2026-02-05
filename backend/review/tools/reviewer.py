"""
代码审查工具
"""
import logging
from typing import Dict, Any
import yaml
from review.tools.base import BaseReviewTool

logger = logging.getLogger(__name__)


class ReviewerTool(BaseReviewTool):
    """代码审查工具"""

    async def run(self, **kwargs) -> Dict[str, Any]:
        """执行代码审查"""
        logger.info(f"Starting review for {self.pr_url}")

        # 获取 PR 信息
        pr_info = self.get_pr_info()

        # 获取配置
        max_findings = self.project_config.get("review_max_findings", config.review["review_max_findings"])
        require_tests = self.project_config.get("review_require_tests", config.review["review_require_tests"])
        require_security = self.project_config.get("review_require_security", config.review["review_require_security"])
        extra_instructions = self.project_config.get("review_extra_instructions", config.review["review_extra_instructions"])

        # 构建参数
        ai_params = {
            **pr_info,
            "diff": self.get_diff_content(max_tokens=self.ai_handler.max_tokens),
            "commits": self.get_commit_messages(),
            "extra_instructions": extra_instructions,
        }

        # 调用 AI
        response = await self.call_ai("review", **ai_params)

        # 解析结果
        result = self._parse_response(response)

        # 发布结果
        await self._publish_result(result)

        return {
            "success": True,
            "result": result,
        }

    def _parse_response(self, response: str) -> Dict[str, Any]:
        """解析 AI 响应"""
        try:
            # 尝试解析 YAML
            if "```yaml" in response:
                yaml_start = response.find("```yaml") + 7
                yaml_end = response.find("```", yaml_start)
                yaml_content = response[yaml_start:yaml_end].strip()
                data = yaml.safe_load(yaml_content)
            elif "```" in response:
                # 尝试提取代码块
                code_start = response.find("```") + 3
                code_end = response.find("```", code_start)
                code_content = response[code_start:code_end].strip()
                data = yaml.safe_load(code_content)
            else:
                data = yaml.safe_load(response)

            return data or {"raw_response": response}
        except Exception as e:
            logger.error(f"Failed to parse YAML response: {e}")
            return {"raw_response": response, "error": str(e)}

    async def _publish_result(self, result: Dict[str, Any]):
        """发布审查结果"""
        # 构建 Markdown 输出
        output = self._format_output(result)

        # 发布到 GitLab
        if config.ai.get("publish_output", True):
            self.provider.publish_persistent_comment(
                output,
                initial_header="## 🤖 Review Agent 审查报告",
            )

    def _format_output(self, result: Dict[str, Any]) -> str:
        """格式化输出"""
        if "raw_response" in result:
            return result["raw_response"]

        output = []

        # 整体评分
        if "overall_score" in result:
            score = result["overall_score"]
            output.append(f"### 整体评分: {score}/10\n")

        # 摘要
        if "summary" in result:
            output.append(f"### 摘要\n{result['summary']}\n")

        # 问题列表
        if "issues" in result and result["issues"]:
            output.append("### 发现的问题\n")
            for issue in result["issues"]:
                severity = issue.get("severity", "suggestion")
                severity_emoji = {
                    "critical": "🔴",
                    "major": "🟠",
                    "minor": "🟡",
                    "suggestion": "💡",
                }.get(severity, "📝")

                output.append(f"{severity_emoji} **{severity.upper()}** - {issue.get('description', 'N/A')}")

                if issue.get("file"):
                    output.append(f"  - 文件: `{issue['file']}`")
                    if issue.get("line"):
                        output.append(f"  - 行号: `{issue['line']}`")

                if issue.get("suggestion"):
                    output.append(f"  - 建议: {issue['suggestion']}")

                output.append("")

        # 工作量估算
        if "effort_estimate" in result:
            effort = result["effort_estimate"]
            effort_desc = {
                "small": "小 (< 1 小时)",
                "medium": "中 (1-4 小时)",
                "large": "大 (4-8 小时)",
                "x-large": "超大 (> 8 小时)",
            }.get(effort, effort)
            output.append(f"### 工作量估算\n{effort_desc}")

        return "\n".join(output)
