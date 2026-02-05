"""
Prompt 模板管理器
"""
import os
from pathlib import Path
from typing import Dict, Any
import yaml

from config.settings import config

# Prompt 模板目录
PROMPTS_DIR = Path(__file__).parent / "prompts"


class PromptManager:
    """Prompt 模板管理器"""

    def __init__(self):
        self._templates: Dict[str, Dict[str, str]] = {}
        self._load_templates()

    def _load_templates(self):
        """加载所有 Prompt 模板"""
        # 加载审查模板
        self._templates["review"] = self._load_yaml("review.yaml")

        # 加载描述模板
        self._templates["describe"] = self._load_yaml("describe.yaml")

        # 加载改进模板
        self._templates["improve"] = self._load_yaml("improve.yaml")

        # 加载问答模板
        self._templates["question"] = self._load_yaml("question.yaml")

    def _load_yaml(self, filename: str) -> Dict[str, str]:
        """加载 YAML 模板文件"""
        filepath = PROMPTS_DIR / filename
        if not filepath.exists():
            # 返回默认模板
            return self._get_default_template(filename)

        with open(filepath, "r", encoding="utf-8") as f:
            return yaml.safe_load(f)

    def _get_default_template(self, filename: str) -> Dict[str, str]:
        """获取默认模板"""
        # 简化的默认模板
        if "review" in filename:
            return {
                "system": """你是一个专业的代码审查员。请审查以下 Pull Request 的代码变更，重点关注：
1. 代码质量和可读性
2. 潜在的 bug 和错误
3. 安全问题
4. 性能优化建议
5. 测试覆盖

请以结构化的方式输出审查结果，包括：
- 整体评价（1-10分）
- 发现的问题（按严重程度分类）
- 改进建议
""",
                "user": """## PR 信息
- 标题: {title}
- 分支: {source_branch} -> {target_branch}

## 描述
{description}

## 代码变更
{diff}

## 提交信息
{commits}
"""
            }
        elif "describe" in filename:
            return {
                "system": "你是一个专业的技术文档撰写者。请根据以下 PR 的代码变更生成一个清晰、专业的 PR 描述。",
                "user": """## 代码变更
{files}

## Diff
{diff}

请生成一个包含以下内容的描述：
- 简短摘要
- 变更类型
- 主要变更列表
"""
            }
        elif "improve" in filename:
            return {
                "system": "你是一个专业的代码优化专家。请分析以下代码并提供具体的改进建议。",
                "user": """## 代码
{code}

请提供：
1. 具体的改进代码
2. 改进理由
3. 预期效果
"""
            }
        else:
            return {
                "system": "你是一个有用的助手。",
                "user": "{content}"
            }

    def get_template(self, review_type: str) -> Dict[str, str]:
        """获取指定类型的模板"""
        return self._templates.get(review_type, self._get_default_template(review_type))

    def render(self, review_type: str, **kwargs) -> tuple:
        """渲染 Prompt 模板"""
        template = self.get_template(review_type)
        system_prompt = template.get("system", "")
        user_prompt = template.get("user", "")

        # 替换变量
        if kwargs:
            for key, value in kwargs.items():
                placeholder = "{" + key + "}"
                system_prompt = system_prompt.replace(placeholder, str(value))
                user_prompt = user_prompt.replace(placeholder, str(value))

        return system_prompt, user_prompt


# 全局实例
prompt_manager = PromptManager()
