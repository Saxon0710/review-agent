"""
Webhook 处理的 Celery 任务
处理来自 GitLab 的 Webhook 事件
"""
import logging
from typing import Dict, Any, Optional
from django.utils import timezone
from django.db import transaction
from core.models import (
    GitLabProject,
    PullRequest,
    GitLabUser,
    ReviewConfiguration,
    ReviewTask,
)
from integration.gitlab.client import GitLabClient
from integration.gitlab.sync import ProjectSyncService
from integration.tasks.celery import app

logger = logging.getLogger(__name__)

# 默认 AI 模型配置
DEFAULT_AI_MODEL = "gpt-4o"


@app.task(name="integration.tasks.jobs.webhook.process_merge_request_event")
def process_merge_request_event(payload: Dict[str, Any]) -> str:
    """
    处理 MR 事件

    Args:
        payload: Webhook 载荷

    Returns:
        处理结果状态
    """
    try:
        action = payload.get("object_attributes", {}).get("action")
        mr_attrs = payload.get("object_attributes", {})
        project_info = payload.get("project", {})

        project_id = project_info.get("id")
        mr_iid = mr_attrs.get("iid")
        project_path = project_info.get("path_with_namespace")

        logger.info(f"Processing MR event: {action} for {project_path}!{mr_iid}")

        # 同步项目（如果需要）
        _ensure_project_synced(project_id, project_path)

        # 同步 MR
        _sync_mr(payload)

        # 根据动作类型处理
        if action in ["open", "reopen"]:
            result = _handle_mr_opened(payload)
        elif action == "update":
            if mr_attrs.get("oldrev"):
                result = _handle_mr_pushed(payload)
            else:
                result = "ignored"
        elif action == "merge":
            result = _handle_mr_merged(payload)
        elif action == "close":
            result = _handle_mr_closed(payload)
        else:
            result = "unknown_action"

        return result

    except Exception as e:
        logger.error(f"Error processing MR event: {e}", exc_info=True)
        return "error"


@app.task(name="integration.tasks.jobs.webhook.process_note_event")
def process_note_event(payload: Dict[str, Any]) -> str:
    """
    处理评论事件

    Args:
        payload: Webhook 载荷

    Returns:
        处理结果状态
    """
    try:
        note = payload.get("note", {})
        noteable_type = note.get("noteable_type")
        note_body = note.get("body", "")

        # 只处理 MR 评论
        if noteable_type != "MergeRequest":
            return "not_merge_request"

        # 检查是否是命令
        if not note_body.strip().startswith("/"):
            return "not_a_command"

        return _handle_command_review(payload)

    except Exception as e:
        logger.error(f"Error processing note event: {e}", exc_info=True)
        return "error"


@app.task(name="integration.tasks.jobs.webhook.trigger_review")
def trigger_review(
    project_id: int,
    mr_iid: int,
    review_type: str = "review",
    triggered_by: str = "webhook",
    options: Optional[Dict[str, Any]] = None,
) -> Optional[str]:
    """
    触发审查任务

    Args:
        project_id: 项目 ID
        mr_iid: MR IID
        review_type: 审查类型
        triggered_by: 触发方式
        options: 额外选项

    Returns:
        任务 ID 或 None
    """
    try:
        # 获取项目
        project = GitLabProject.objects.get(project_id=project_id)

        # 获取或自动创建配置
        config = _get_or_create_config(project)

        # 获取或创建 PR
        mr, _ = PullRequest.objects.get_or_create(
            project=project,
            mr_iid=mr_iid,
            defaults={
                "mr_id": mr_iid,
                "title": f"MR {mr_iid}",
                "state": "opened",
                "url": f"{project.url}/-/merge_requests/{mr_iid}",
                "source_branch": "",
                "target_branch": "",
                "gitlab_created_at": timezone.now(),
                "gitlab_updated_at": timezone.now(),
            },
        )

        # 检查是否应该忽略
        if _should_ignore_review(mr, config):
            logger.info(f"Review ignored for {project.path_with_namespace}!{mr_iid}")
            return None

        # 创建审查任务
        task = ReviewTask.objects.create(
            pull_request=mr,
            review_type=review_type,
            status="pending",
            triggered_by=triggered_by,
            options=options or {},
            ai_model=config.ai_model,
        )

        # 异步执行审查
        from integration.tasks.jobs.review import ReviewTaskRunner

        app.get_task("integration.tasks.jobs.review.execute_review").apply_async(
            args=[str(task.task_id)],
        )

        logger.info(
            f"Review task {task.task_id} created for {project.path_with_namespace}!{mr_iid}"
        )

        return str(task.task_id)

    except Exception as e:
        logger.error(f"Error triggering review: {e}", exc_info=True)
        return None


# ========== 内部辅助函数 ==========


def _get_or_create_config(project: GitLabProject) -> ReviewConfiguration:
    """
    获取或自动创建项目审查配置

    对于全局 webhook 监听的项目，自动创建默认配置并启用自动审查

    Args:
        project: GitLab 项目

    Returns:
        ReviewConfiguration 实例
    """
    config, created = ReviewConfiguration.objects.get_or_create(
        project=project,
        defaults={
            # 自动审查配置 - 默认启用
            "auto_review_on_open": True,
            "auto_review_commands": ["/review", "/describe"],
            "auto_review_on_push": True,
            "auto_review_push_commands": ["/review"],
            # Push 事件监听配置 - 空列表表示监听所有分支
            "watch_push_branches": [],
            # 忽略规则 - 默认忽略草稿 MR
            "ignore_draft": True,
            "ignore_title_patterns": [],
            "ignore_branch_patterns": [],
            "ignore_label_patterns": [],
            "ignore_file_patterns": [],
            # 审查参数 - 使用合理的默认值
            "review_extra_instructions": "",
            "review_max_findings": 5,
            "review_require_tests": True,
            "review_require_security": True,
            "review_require_estimate_effort": True,
            # AI 配置
            "ai_model": DEFAULT_AI_MODEL,
            "ai_temperature": 0.2,
            "ai_max_tokens": 16000,
            # 输出配置
            "publish_output": True,
            "publish_inline_comments": True,
            "use_persistent_comment": True,
            # 其他配置
            "verbosity_level": 0,
            "enable_auto_approval": False,
            "auto_approve_threshold": 9,
        },
    )

    if created:
        logger.info(
            f"Auto-created review configuration for project {project.path_with_namespace} "
            f"(auto_review_on_open=True, auto_review_on_push=True, watch_push_branches=[])"
        )

    return config


def _ensure_project_synced(project_id: int, project_path: str) -> bool:
    """确保项目已同步"""
    try:
        project, created = GitLabProject.objects.get_or_create(
            project_id=project_id,
            defaults={
                "name": project_path.split("/")[-1],
                "path_with_namespace": project_path,
                "url": f"https://gitlab.com/{project_path}",
                "is_active": True,
            },
        )

        if created:
            logger.info(f"Created new project record: {project_path}")

        return True

    except Exception as e:
        logger.error(f"Error ensuring project synced: {e}")
        return False


def _sync_mr(payload: Dict[str, Any]) -> bool:
    """同步 MR 信息"""
    try:
        mr_attrs = payload.get("object_attributes", {})
        project_info = payload.get("project", {})
        user_info = payload.get("user", {})

        project_id = project_info.get("id")
        mr_iid = mr_attrs.get("iid")

        project = GitLabProject.objects.get(project_id=project_id)

        # 获取或创建用户
        gitlab_user = None
        if user_info:
            gitlab_user, _ = GitLabUser.objects.get_or_create(
                gitlab_user_id=user_info.get("id", 0),
                defaults={
                    "gitlab_username": user_info.get("username", ""),
                    "gitlab_email": user_info.get("email", ""),
                },
            )

        # 更新或创建 MR
        mr, created = PullRequest.objects.update_or_create(
            project=project,
            mr_iid=mr_iid,
            defaults={
                "mr_id": mr_attrs.get("id", mr_iid),
                "title": mr_attrs.get("title", ""),
                "description": mr_attrs.get("description", ""),
                "source_branch": mr_attrs.get("source_branch", ""),
                "target_branch": mr_attrs.get("target_branch", ""),
                "state": mr_attrs.get("state", "opened"),
                "draft": mr_attrs.get("draft", False) or mr_attrs.get("work_in_progress", False),
                "url": mr_attrs.get("url", ""),
                "author": gitlab_user,
                "gitlab_created_at": mr_attrs.get("created_at"),
                "gitlab_updated_at": mr_attrs.get("updated_at"),
            },
        )

        if created:
            logger.info(f"Created MR record: {project.path_with_namespace}!{mr_iid}")
        else:
            logger.debug(f"Updated MR record: {project.path_with_namespace}!{mr_iid}")

        return True

    except Exception as e:
        logger.error(f"Error syncing MR: {e}")
        return False


def _handle_mr_opened(payload: Dict[str, Any]) -> str:
    """
    处理 MR 打开事件

    全局 webhook 模式下，自动为项目创建配置并触发审查
    """
    try:
        project_info = payload.get("project", {})
        mr_attrs = payload.get("object_attributes", {})

        project_id = project_info.get("id")
        mr_iid = mr_attrs.get("iid")

        project = GitLabProject.objects.get(project_id=project_id)

        # 获取或自动创建配置（全局 webhook 模式）
        config = _get_or_create_config(project)

        # 检查是否配置了自动审查（默认已启用）
        if config.auto_review_on_open:
            trigger_review.delay(
                project_id=project_id,
                mr_iid=mr_iid,
                review_type="review",
                triggered_by="webhook",
            )
            return "review_triggered"
        else:
            return "auto_review_disabled"

    except Exception as e:
        logger.error(f"Error handling MR opened: {e}", exc_info=True)
        return "error"


def _handle_mr_pushed(payload: Dict[str, Any]) -> str:
    """
    处理 MR 推送事件

    全局 webhook 模式下，自动为项目创建配置并触发审查
    """
    try:
        project_info = payload.get("project", {})
        mr_attrs = payload.get("object_attributes", {})

        project_id = project_info.get("id")
        mr_iid = mr_attrs.get("iid")

        project = GitLabProject.objects.get(project_id=project_id)

        # 获取或自动创建配置（全局 webhook 模式）
        config = _get_or_create_config(project)

        # 检查是否配置了推送时自动审查（默认已启用）
        if config.auto_review_on_push:
            trigger_review.delay(
                project_id=project_id,
                mr_iid=mr_iid,
                review_type="review",
                triggered_by="webhook",
            )
            return "review_triggered"
        else:
            return "auto_review_disabled"

    except Exception as e:
        logger.error(f"Error handling MR pushed: {e}", exc_info=True)
        return "error"


def _handle_mr_merged(payload: Dict[str, Any]) -> str:
    """处理 MR 已合并事件"""
    try:
        project_info = payload.get("project", {})
        mr_attrs = payload.get("object_attributes", {})

        project_id = project_info.get("id")
        mr_iid = mr_attrs.get("iid")

        # 更新 MR 状态
        project = GitLabProject.objects.get(project_id=project_id)

        PullRequest.objects.filter(
            project=project,
            mr_iid=mr_iid,
        ).update(
            state="merged",
            merged_at=mr_attrs.get("merged_at"),
        )

        return "updated"

    except Exception as e:
        logger.error(f"Error handling MR merged: {e}", exc_info=True)
        return "error"


def _handle_mr_closed(payload: Dict[str, Any]) -> str:
    """处理 MR 已关闭事件"""
    try:
        project_info = payload.get("project", {})
        mr_attrs = payload.get("object_attributes", {})

        project_id = project_info.get("id")
        mr_iid = mr_attrs.get("iid")

        # 更新 MR 状态
        project = GitLabProject.objects.get(project_id=project_id)

        PullRequest.objects.filter(
            project=project,
            mr_iid=mr_iid,
        ).update(
            state="closed",
            closed_at=mr_attrs.get("closed_at") or timezone.now(),
        )

        # 取消待处理的任务
        ReviewTask.objects.filter(
            pull_request__project=project,
            pull_request__mr_iid=mr_iid,
            status__in=["pending", "queued"],
        ).update(
            status="cancelled",
            completed_at=timezone.now(),
        )

        return "updated"

    except Exception as e:
        logger.error(f"Error handling MR closed: {e}", exc_info=True)
        return "error"


def _handle_command_review(payload: Dict[str, Any]) -> str:
    """
    处理命令审查

    支持的命令:
    - /review: 代码审查
    - /describe: 生成描述
    - /improve: 改进建议
    - /explain: 解释代码
    - /question: 提问
    """
    try:
        note = payload.get("note", {})
        note_body = note.get("body", "").strip()
        mr_attrs = payload.get("object_attributes", {})
        project_info = payload.get("project", {})

        project_id = project_info.get("id")
        mr_iid = mr_attrs.get("iid")

        # 解析命令
        parts = note_body.split()
        command = parts[0].lower()
        args = parts[1:] if len(parts) > 1 else []

        # 映射命令到审查类型
        review_type = "review"
        if command == "/review":
            review_type = "review"
        elif command == "/describe":
            review_type = "describe"
        elif command == "/improve":
            review_type = "improve"
        elif command == "/explain":
            review_type = "describe"
        elif command.startswith("/question"):
            review_type = "question"
        else:
            return "unknown_command"

        # 触发审查（命令审查总是执行，不管配置如何）
        options = {}
        if review_type == "question" and args:
            options["question"] = " ".join(args)

        trigger_review.delay(
            project_id=project_id,
            mr_iid=mr_iid,
            review_type=review_type,
            triggered_by="command",
            options=options,
        )

        return "review_triggered"

    except Exception as e:
        logger.error(f"Error handling command review: {e}", exc_info=True)
        return "error"


def _should_ignore_review(mr: PullRequest, config: ReviewConfiguration) -> bool:
    """检查是否应该忽略审查"""
    import re

    # 检查草稿 MR
    if config.ignore_draft and mr.draft:
        return True

    # 检查标题模式
    if config.ignore_title_patterns:
        title = mr.title.lower()
        for pattern in config.ignore_title_patterns:
            if re.search(pattern.lower(), title):
                return True

    # 检查分支模式
    if config.ignore_branch_patterns and mr.source_branch:
        source = mr.source_branch.lower()
        for pattern in config.ignore_branch_patterns:
            if re.search(pattern.lower(), source):
                return True

    return False


def _should_watch_branch(branch_name: str, config: ReviewConfiguration) -> bool:
    """
    检查是否应该监听该分支的 push 事件

    Args:
        branch_name: 分支名称
        config: 审查配置

    Returns:
        是否监听该分支
    """
    watch_branches = config.watch_push_branches or []

    # 空列表表示监听所有分支
    if not watch_branches:
        return True

    # 检查分支是否在监听列表中
    return branch_name in watch_branches


@app.task(name="integration.tasks.jobs.webhook.process_push_event")
def process_push_event(payload: Dict[str, Any]) -> str:
    """
    处理 Push 事件

    监听指定分支的 push 事件，可以用于：
    - 直接分支的代码审查（非 MR 场景）
    - 持续集成的代码质量检查
    - 主分支的自动化审查

    注意：Push 事件独立处理，不管该分支是否有 MR

    Args:
        payload: Webhook 载荷

    Returns:
        处理结果状态
    """
    try:
        project_info = payload.get("project", {})
        ref = payload.get("ref", "")
        project_id = project_info.get("id")
        project_path = project_info.get("path_with_namespace", "")

        # 提取分支名称 (ref 格式: refs/heads/branch-name)
        if ref.startswith("refs/heads/"):
            branch_name = ref[len("refs/heads/"):]
        else:
            return "invalid_ref"

        # 检查是否是删除分支的 push
        if payload.get("checkout_sha") is None:
            return "branch_deleted"

        logger.info(f"Processing push event: {project_path}:{branch_name}")

        # 同步项目
        _ensure_project_synced(project_id, project_path)

        # 获取项目
        project = GitLabProject.objects.get(project_id=project_id)

        # 获取或创建配置
        config = _get_or_create_config(project)

        # 检查是否应该监听该分支
        if not _should_watch_branch(branch_name, config):
            logger.info(f"Branch {branch_name} not in watch list, ignoring")
            return "branch_not_watched"

        # 获取 push 信息
        commits = payload.get("commits", [])
        total_commits_count = payload.get("total_commits_count", len(commits))

        if total_commits_count == 0:
            return "no_commits"

        # Push 事件独立处理，不管是否有 MR
        # 触发分支审查任务
        task_id = _trigger_branch_review(
            project=project,
            branch_name=branch_name,
            commit_count=total_commits_count,
            payload=payload,
        )

        if task_id:
            logger.info(f"Branch review task {task_id} created for {project_path}:{branch_name}")
            return "review_triggered"
        else:
            return "review_skipped"

    except Exception as e:
        logger.error(f"Error processing push event: {e}", exc_info=True)
        return "error"


def _trigger_branch_review(
    project: GitLabProject,
    branch_name: str,
    commit_count: int,
    payload: Dict[str, Any],
) -> Optional[str]:
    """
    触发分支审查（非 MR 场景）

    Args:
        project: GitLab 项目
        branch_name: 分支名称
        commit_count: 提交数量
        payload: Push 事件载荷

    Returns:
        任务 ID 或 None
    """
    try:
        config = _get_or_create_config(project)

        # 获取最新的 commit 信息
        commits = payload.get("commits", [])
        latest_commit = commits[-1] if commits else {}
        commit_id = latest_commit.get("id", payload.get("checkout_sha", ""))
        commit_message = latest_commit.get("message", "")
        commit_author = latest_commit.get("author", {}).get("name", "Unknown")

        # 创建或更新分支记录（复用 PullRequest 模型）
        # 对于非 MR 的分支审查，我们创建一个特殊的记录
        mr, created = PullRequest.objects.get_or_create(
            project=project,
            mr_iid=0,  # 使用 0 表示非 MR 的分支审查
            source_branch=branch_name,
            defaults={
                "mr_id": 0,
                "title": f"[Branch Review] {branch_name}",
                "description": f"Branch review triggered by push event\n\nCommit: {commit_id[:8]}\nAuthor: {commit_author}\nMessage: {commit_message[:200]}",
                "target_branch": "",
                "state": "opened",
                "draft": False,
                "url": f"{project.url}/-/tree/{branch_name}",
                "gitlab_created_at": timezone.now(),
                "gitlab_updated_at": timezone.now(),
            },
        )

        # 更新已有记录
        if not created:
            mr.description = f"Branch review triggered by push event\n\nCommit: {commit_id[:8]}\nAuthor: {commit_author}\nMessage: {commit_message[:200]}"
            mr.gitlab_updated_at = timezone.now()
            mr.save()

        # 创建审查任务
        task = ReviewTask.objects.create(
            pull_request=mr,
            review_type="review",
            status="pending",
            triggered_by="push",
            options={
                "branch_name": branch_name,
                "commit_id": commit_id,
                "commit_count": commit_count,
                "is_branch_review": True,  # 标记为分支审查
            },
            ai_model=config.ai_model,
        )

        # 异步执行审查
        from integration.tasks.jobs.review import ReviewTaskRunner

        app.get_task("integration.tasks.jobs.review.execute_review").apply_async(
            args=[str(task.task_id)],
        )

        return str(task.task_id)

    except Exception as e:
        logger.error(f"Error triggering branch review: {e}", exc_info=True)
        return None
