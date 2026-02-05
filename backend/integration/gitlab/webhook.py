"""GitLab Webhook 处理器"""
import logging
import hmac
import hashlib
from typing import Dict, Any, Optional
from dataclasses import dataclass

from config.settings import settings

logger = logging.getLogger(__name__)


@dataclass
class WebhookEvent:
    """Webhook 事件数据类"""
    event_type: str
    object_kind: str
    project_id: int
    project_path: str
    mr_iid: Optional[int] = None
    mr_state: Optional[str] = None
    mr_draft: bool = False
    action: Optional[str] = None
    user_id: Optional[int] = None
    user_username: Optional[str] = None


class WebhookProcessor:
    """GitLab Webhook 处理器"""

    def __init__(self, secret: Optional[str] = None):
        """
        初始化 Webhook 处理器

        Args:
            secret: Webhook 密钥，用于验证签名
        """
        self.secret = secret or settings.get("gitlab.webhook_secret")

    def verify_signature(self, payload: bytes, signature: str) -> bool:
        """
        验证 Webhook 签名

        Args:
            payload: 原始请求体
            signature: X-Gitlab-Token 头的值

        Returns:
            验证是否通过
        """
        if not self.secret:
            # 如果没有配置密钥，跳过验证
            logger.warning("Webhook secret not configured, skipping verification")
            return True

        expected = hmac.new(
            self.secret.encode(),
            payload,
            hashlib.sha256,
        ).hexdigest()

        # GitLab 使用简单的 token 对比
        return hmac.compare_digest(signature, self.secret)

    def parse_event(self, headers: Dict[str, str], body: Dict[str, Any]) -> Optional[WebhookEvent]:
        """
        解析 Webhook 事件

        Args:
            headers: 请求头
            body: 请求体 JSON

        Returns:
            WebhookEvent 对象，解析失败返回 None
        """
        try:
            object_kind = body.get("object_kind")

            # 获取项目信息
            project = body.get("project", {})
            project_id = project.get("id")
            project_path = project.get("path_with_namespace")

            if not project_id:
                logger.error("Missing project_id in webhook payload")
                return None

            # 处理 MR 事件
            if object_kind == "merge_request":
                return self._parse_mr_event(body, project_id, project_path)

            # 处理 Note 事件 (评论)
            elif object_kind == "note":
                return self._parse_note_event(body, project_id, project_path)

            # 其他事件类型
            else:
                logger.info(f"Unhandled event type: {object_kind}")
                return WebhookEvent(
                    event_type=object_kind,
                    object_kind=object_kind,
                    project_id=project_id,
                    project_path=project_path,
                )

        except Exception as e:
            logger.error(f"Failed to parse webhook event: {e}")
            return None

    def _parse_mr_event(self, body: Dict[str, Any], project_id: int, project_path: str) -> WebhookEvent:
        """解析 MR 事件"""
        mr_attrs = body.get("object_attributes", {})

        return WebhookEvent(
            event_type="merge_request",
            object_kind="merge_request",
            project_id=project_id,
            project_path=project_path,
            mr_iid=mr_attrs.get("iid"),
            mr_state=mr_attrs.get("state"),
            mr_draft=mr_attrs.get("draft", False) or mr_attrs.get("work_in_progress", False),
            action=mr_attrs.get("action"),
            user_id=body.get("user", {}).get("id"),
            user_username=body.get("user", {}).get("username"),
        )

    def _parse_note_event(self, body: Dict[str, Any], project_id: int, project_path: str) -> WebhookEvent:
        """解析 Note (评论) 事件"""
        note_attrs = body.get("object_attributes", {})
        noteable_type = note_attrs.get("noteable_type")

        event = WebhookEvent(
            event_type="note",
            object_kind="note",
            project_id=project_id,
            project_path=project_path,
            action=note_attrs.get("action"),
            user_id=body.get("user", {}).get("id"),
            user_username=body.get("user", {}).get("username"),
        )

        # 如果是 MR 评论
        if noteable_type == "MergeRequest":
            mr_attrs = note_attrs.get("merge_request", {})
            event.mr_iid = mr_attrs.get("iid")
            event.mr_state = mr_attrs.get("state")
            event.mr_draft = mr_attrs.get("draft", False)

        return event

    def should_trigger_review(self, event: WebhookEvent, config: Dict[str, Any]) -> bool:
        """
        判断是否应该触发审查

        Args:
            event: Webhook 事件
            config: 项目审查配置

        Returns:
            是否触发审查
        """
        # 检查是否是 MR 事件
        if event.event_type != "merge_request":
            return False

        # 检查事件动作
        if event.action not in ["open", "update", "reopen"]:
            return False

        # 检查是否忽略草稿
        if event.mr_draft and config.get("ignore_draft", True):
            logger.info(f"Skipping draft MR {event.mr_iid}")
            return False

        # 检查 MR 状态
        if event.mr_state != "opened":
            logger.info(f"MR {event.mr_iid} is not opened (state: {event.mr_state})")
            return False

        # 检查触发条件
        auto_review_on_open = config.get("auto_review_on_open", False)
        auto_review_on_push = config.get("auto_review_on_push", False)

        if event.action == "open" and auto_review_on_open:
            return True

        if event.action == "update" and auto_review_on_push:
            return True

        return False

    def extract_command(self, event: WebhookEvent, body: Dict[str, Any]) -> Optional[str]:
        """
        从评论中提取审查命令

        支持的命令:
        - /review - 代码审查
        - /describe - 生成描述
        - /improve - 改进建议
        - /ask <问题> - 问答

        Args:
            event: Webhook 事件
            body: 请求体 JSON

        Returns:
            命令类型或 None
        """
        if event.event_type != "note":
            return None

        note_attrs = body.get("object_attributes", {})
        note = note_attrs.get("note", "")
        noteable_type = note_attrs.get("noteable_type")

        # 只处理 MR 评论
        if noteable_type != "MergeRequest":
            return None

        # 提取命令
        note = note.strip().lower()

        if note.startswith("/review"):
            return "review"
        elif note.startswith("/describe"):
            return "describe"
        elif note.startswith("/improve"):
            return "improve"
        elif note.startswith("/ask"):
            return "question"

        return None

    def extract_question(self, body: Dict[str, Any]) -> Optional[str]:
        """从 /ask 命令中提取问题"""
        note_attrs = body.get("object_attributes", {})
        note = note_attrs.get("note", "")

        if note.lower().startswith("/ask"):
            # 提取问题部分
            parts = note.split(None, 1)
            if len(parts) > 1:
                return parts[1].strip()

        return None


# 全局实例
webhook_processor = WebhookProcessor()
