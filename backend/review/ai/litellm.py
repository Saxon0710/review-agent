"""
AI 服务 - LiteLLM Handler
基于 PR-Agent 的 LiteLLMAIHandler 实现
"""
import logging
from typing import Tuple, Optional
from pr_agent.algo.ai_handlers.litellm_ai_handler import LiteLLMAIHandler as PRALiteLLMHandler
from config.settings import config

logger = logging.getLogger(__name__)


class LiteLLMHandler(PRALiteLLMHandler):
    """LiteLLM AI Handler 实现"""

    def __init__(self, project_config: dict = None):
        """
        初始化 AI Handler

        Args:
            project_config: 项目特定配置，可覆盖默认配置
        """
        self.project_config = project_config or {}

        # 合并配置：项目配置优先，然后是全局配置
        self.ai_config = self._merge_config()

        # 调用父类初始化（PR-Agent 的实现）
        super().__init__()

    def _merge_config(self) -> dict:
        """合并 AI 配置"""
        global_config = {
            "model": config.ai["model"],
            "temperature": config.ai["temperature"],
            "max_tokens": config.ai["max_tokens"],
            "timeout": config.ai["timeout"],
        }

        # 项目配置覆盖
        global_config.update(self.project_config)

        return global_config

    async def chat_completion(
        self,
        model: str = None,
        system: str = "",
        user: str = "",
        temperature: float = None,
        img_path: str = None,
    ) -> Tuple[str, str]:
        """
        执行 AI 聊天完成

        Args:
            model: 模型名称
            system: 系统提示词
            user: 用户提示词
            temperature: 温度参数
            img_path: 图片路径（可选）

        Returns:
            (response_text, finish_reason)
        """
        # 使用配置的模型
        if model is None:
            model = self.ai_config.get("model", config.ai["model"])

        # 使用配置的温度
        if temperature is None:
            temperature = self.ai_config.get("temperature", config.ai["temperature"])

        # 记录使用信息
        logger.info(f"AI Request: model={model}, temperature={temperature}")

        try:
            # 调用父类方法
            response, finish_reason = await super().chat_completion(
                model=model,
                system=system,
                user=user,
                temperature=temperature,
                img_path=img_path,
            )

            return response, finish_reason

        except Exception as e:
            logger.error(f"AI request failed: {e}")

            # 尝试使用备用模型
            fallback_models = config.ai.get("fallback_models", [])
            for fallback_model in fallback_models:
                if fallback_model != model:
                    logger.info(f"Trying fallback model: {fallback_model}")
                    try:
                        response, finish_reason = await super().chat_completion(
                            model=fallback_model,
                            system=system,
                            user=user,
                            temperature=temperature,
                            img_path=img_path,
                        )
                        return response, finish_reason
                    except Exception as fallback_error:
                        logger.warning(f"Fallback model {fallback_model} also failed: {fallback_error}")

            raise

    def get_model_config(self) -> dict:
        """获取当前模型配置"""
        return self.ai_config.copy()

    @property
    def max_tokens(self) -> int:
        """获取最大 Token 数"""
        return self.ai_config.get("max_tokens", config.ai["max_tokens"])
