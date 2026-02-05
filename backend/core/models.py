"""
Core Models - 数据模型定义
"""
from django.db import models
from django.contrib.auth import get_user_model
from django.core.validators import MinValueValidator, MaxValueValidator
from django.utils import timezone
import uuid
import json


# 获取 Django 用户模型
User = get_user_model()


class TimeStampedModel(models.Model):
    """抽象基类 - 时间戳"""
    created_at = models.DateTimeField(auto_now_add=True, db_index=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        abstract = True


class GitLabProject(TimeStampedModel):
    """GitLab 项目模型"""

    class ProjectVisibility(models.TextChoices):
        PUBLIC = "public", "公开"
        PRIVATE = "private", "私有"
        INTERNAL = "internal", "内部"

    # GitLab 原始信息
    project_id = models.PositiveIntegerField(unique=True, db_index=True)
    name = models.CharField(max_length=255)
    path_with_namespace = models.CharField(max_length=500, unique=True)
    description = models.TextField(blank=True)
    url = models.URLField(max_length=500)
    visibility = models.CharField(max_length=20, choices=ProjectVisibility.choices, default=ProjectVisibility.PRIVATE)
    default_branch = models.CharField(max_length=255, default="main")

    # Webhook 配置
    webhook_url = models.URLField(max_length=500, null=True, blank=True)
    webhook_secret = models.CharField(max_length=100, null=True, blank=True)
    webhook_enabled = models.BooleanField(default=False)

    # 状态
    is_active = models.BooleanField(default=True, db_index=True)
    last_sync_at = models.DateTimeField(null=True, blank=True)

    # 配置 (JSON 格式存储额外的项目配置)
    settings = models.JSONField(default=dict, blank=True)

    # 统计
    mr_count = models.PositiveIntegerField(default=0)
    review_count = models.PositiveIntegerField(default=0)

    class Meta:
        db_table = "gitlab_projects"
        ordering = ["name"]
        indexes = [
            models.Index(fields=["path_with_namespace"]),
            models.Index(fields=["is_active", "last_sync_at"]),
        ]

    def __str__(self):
        return self.path_with_namespace

    @property
    def review_config(self):
        """获取项目审查配置"""
        if not hasattr(self, '_config_cache'):
            self._config_cache = getattr(self, 'config', None)
        return self._config_cache


class GitLabUser(TimeStampedModel):
    """GitLab 用户映射"""

    user = models.OneToOneField(User, on_delete=models.CASCADE, related_name="gitlab_profile")
    gitlab_user_id = models.PositiveIntegerField(unique=True, db_index=True)
    gitlab_username = models.CharField(max_length=255, db_index=True)
    gitlab_email = models.EmailField(null=True, blank=True)
    avatar_url = models.URLField(max_length=500, null=True, blank=True)

    # OAuth 凭证
    access_token = models.CharField(max_length=500, null=True, blank=True)
    refresh_token = models.CharField(max_length=500, null=True, blank=True)
    token_expires_at = models.DateTimeField(null=True, blank=True)

    # 状态
    is_active = models.BooleanField(default=True)
    last_login_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "gitlab_users"
        ordering = ["gitlab_username"]
        indexes = [
            models.Index(fields=["gitlab_user_id"]),
            models.Index(fields=["gitlab_username"]),
        ]

    def __str__(self):
        return f"@{self.gitlab_username}"


class PullRequest(TimeStampedModel):
    """合并请求 (MR) 模型"""

    class State(models.TextChoices):
        OPENED = "opened", "开启"
        CLOSED = "closed", "关闭"
        MERGED = "merged", "已合并"
        LOCKED = "locked", "锁定"

    # 关联项目
    project = models.ForeignKey(GitLabProject, on_delete=models.CASCADE, related_name="pull_requests", db_index=True)

    # GitLab 原始信息
    mr_id = models.PositiveIntegerField(db_index=True)
    mr_iid = models.PositiveIntegerField(db_index=True)  # MR IID (项目内唯一)
    title = models.CharField(max_length=500)
    description = models.TextField(blank=True)

    # 分支信息
    source_branch = models.CharField(max_length=255)
    target_branch = models.CharField(max_length=255)

    # 作者
    author = models.ForeignKey(GitLabUser, on_delete=models.SET_NULL, null=True, blank=True, related_name="authored_mrs")
    assignee = models.ForeignKey(GitLabUser, on_delete=models.SET_NULL, null=True, blank=True, related_name="assigned_mrs")

    # 状态
    state = models.CharField(max_length=20, choices=State.choices, default=State.OPENED, db_index=True)
    draft = models.BooleanField(default=False, db_index=True)

    # URL
    url = models.URLField(max_length=500)

    # 时间 (GitLab 原始时间)
    gitlab_created_at = models.DateTimeField()
    gitlab_updated_at = models.DateTimeField()
    merged_at = models.DateTimeField(null=True, blank=True)
    closed_at = models.DateTimeField(null=True, blank=True)

    # 统计
    additions = models.PositiveIntegerField(default=0)
    deletions = models.PositiveIntegerField(default=0)
    changed_files = models.PositiveIntegerField(default=0)

    # 最后审查时间
    last_reviewed_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "pull_requests"
        ordering = ["-gitlab_created_at"]
        unique_together = [["project", "mr_iid"]]
        indexes = [
            models.Index(fields=["project", "state"]),
            models.Index(fields=["project", "draft", "state"]),
            models.Index(fields=["-gitlab_created_at"]),
        ]

    def __str__(self):
        return f"{self.project.path_with_namespace}!{self.mr_iid}: {self.title}"

    @property
    def is_open(self):
        return self.state == self.State.OPENED

    @property
    def is_merged(self):
        return self.state == self.State.MERGED


class ReviewTask(TimeStampedModel):
    """审查任务模型"""

    class Status(models.TextChoices):
        PENDING = "pending", "待处理"
        QUEUED = "queued", "队列中"
        RUNNING = "running", "执行中"
        COMPLETED = "completed", "已完成"
        FAILED = "failed", "失败"
        CANCELLED = "cancelled", "已取消"

    class ReviewType(models.TextChoices):
        REVIEW = "review", "代码审查"
        DESCRIBE = "describe", "描述生成"
        IMPROVE = "improve", "代码改进"
        QUESTION = "question", "问答"
        UPDATE_CHANGELOG = "update_changelog", "更新日志"
        GENERATE_LABELS = "generate_labels", "生成标签"

    # 关联 PR
    pull_request = models.ForeignKey(PullRequest, on_delete=models.CASCADE, related_name="review_tasks", db_index=True)

    # 任务标识
    task_id = models.UUIDField(default=uuid.uuid4, unique=True, db_index=True)

    # 审查类型
    review_type = models.CharField(max_length=20, choices=ReviewType.choices, db_index=True)

    # 状态
    status = models.CharField(max_length=20, choices=Status.choices, default=Status.PENDING, db_index=True)

    # 触发信息
    triggered_by = models.CharField(max_length=50)  # webhook, manual, schedule
    trigger_user = models.ForeignKey(GitLabUser, on_delete=models.SET_NULL, null=True, blank=True, related_name="triggered_tasks")

    # 参数配置
    options = models.JSONField(default=dict, blank=True)

    # 执行结果
    result = models.JSONField(null=True, blank=True)
    output = models.TextField(blank=True)  # Markdown 格式输出

    # 错误信息
    error_message = models.TextField(blank=True)
    error_code = models.CharField(max_length=50, null=True, blank=True)

    # 执行时间
    started_at = models.DateTimeField(null=True, blank=True)
    completed_at = models.DateTimeField(null=True, blank=True)

    # 统计
    duration_seconds = models.PositiveIntegerField(null=True, blank=True)
    tokens_used = models.PositiveIntegerField(default=0)

    # AI 配置快照
    ai_model = models.CharField(max_length=100, null=True, blank=True)
    ai_temperature = models.FloatField(null=True, blank=True)

    class Meta:
        db_table = "review_tasks"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["pull_request", "-created_at"]),
            models.Index(fields=["status", "-created_at"]),
            models.Index(fields=["review_type", "-created_at"]),
            models.Index(fields=["task_id"]),
        ]

    def __str__(self):
        return f"{self.review_type} - {self.pull_request} - {self.status}"

    @property
    def duration(self):
        """计算任务耗时"""
        if self.started_at and self.completed_at:
            return (self.completed_at - self.started_at).total_seconds()
        return None


class ReviewComment(TimeStampedModel):
    """审查评论模型"""

    class CommentType(models.TextChoices):
        OVERALL = "overall", "整体评论"
        FILE = "file", "文件评论"
        LINE = "line", "行内评论"

    # 关联任务
    task = models.ForeignKey(ReviewTask, on_delete=models.CASCADE, related_name="comments", db_index=True)

    # GitLab 评论 ID (发布后回填)
    comment_id = models.PositiveIntegerField(null=True, blank=True)
    discussion_id = models.CharField(max_length=100, null=True, blank=True)

    # 评论类型
    comment_type = models.CharField(max_length=20, choices=CommentType.choices, default=CommentType.OVERALL)

    # 文件信息 (文件/行内评论)
    file_path = models.CharField(max_length=500, null=True, blank=True)
    line_start = models.PositiveIntegerField(null=True, blank=True)
    line_end = models.PositiveIntegerField(null=True, blank=True)
    side = models.CharField(max_length=10, null=True, blank=True)  # LEFT, RIGHT

    # 持久化评论
    is_persistent = models.BooleanField(default=False)

    # 评论内容
    body = models.TextField()

    # 是否发布
    is_published = models.BooleanField(default=True)
    published_at = models.DateTimeField(null=True, blank=True)

    class Meta:
        db_table = "review_comments"
        ordering = ["id"]
        indexes = [
            models.Index(fields=["task", "comment_type"]),
            models.Index(fields=["file_path"]),
        ]

    def __str__(self):
        return f"Comment on {self.task.task_id}"


class ReviewConfiguration(TimeStampedModel):
    """项目审查配置"""

    # 关联项目 (一对一)
    project = models.OneToOneField(GitLabProject, on_delete=models.CASCADE, related_name="config")

    # ========== 自动审查配置 ==========
    auto_review_on_open = models.BooleanField(default=False, verbose_name="MR 打开时自动审查")
    auto_review_commands = models.JSONField(default=list, blank=True, verbose_name="自动审查命令")

    auto_review_on_push = models.BooleanField(default=False, verbose_name="推送时自动审查")
    auto_review_push_commands = models.JSONField(default=list, blank=True, verbose_name="推送审查命令")

    # Push 事件监听配置
    watch_push_branches = models.JSONField(
        default=list,
        blank=True,
        verbose_name="监听 Push 的分支",
        help_text="空列表表示监听所有分支，否则只监听列表中的分支"
    )

    # ========== 忽略规则 ==========
    ignore_draft = models.BooleanField(default=True, verbose_name="忽略草稿 MR")
    ignore_title_patterns = models.JSONField(default=list, blank=True, verbose_name="忽略标题模式")
    ignore_branch_patterns = models.JSONField(default=list, blank=True, verbose_name="忽略分支模式")
    ignore_label_patterns = models.JSONField(default=list, blank=True, verbose_name="忽略标签模式")
    ignore_file_patterns = models.JSONField(default=list, blank=True, verbose_name="忽略文件模式")

    # ========== 审查参数 ==========
    review_extra_instructions = models.TextField(blank=True, verbose_name="额外审查指令")
    review_max_findings = models.PositiveIntegerField(default=3, verbose_name="最大发现问题数")
    review_require_tests = models.BooleanField(default=True, verbose_name="要求测试审查")
    review_require_security = models.BooleanField(default=True, verbose_name="要求安全审查")
    review_require_estimate_effort = models.BooleanField(default=True, verbose_name="要求估算工作量")

    # ========== AI 配置 ==========
    ai_model = models.CharField(max_length=100, default="gpt-4o", verbose_name="AI 模型")
    ai_temperature = models.FloatField(default=0.2, verbose_name="AI 温度参数")
    ai_max_tokens = models.PositiveIntegerField(default=16000, verbose_name="最大 Token 数")

    # ========== 输出配置 ==========
    publish_output = models.BooleanField(default=True, verbose_name="发布输出")
    publish_inline_comments = models.BooleanField(default=True, verbose_name="发布行内评论")
    use_persistent_comment = models.BooleanField(default=True, verbose_name="使用持久化评论")

    # ========== 其他配置 ==========
    verbosity_level = models.IntegerField(default=0, verbose_name="详细程度")
    enable_auto_approval = models.BooleanField(default=False, verbose_name="启用自动审批")
    auto_approve_threshold = models.IntegerField(default=9, verbose_name="自动审批阈值")

    class Meta:
        db_table = "review_configurations"
        verbose_name = "审查配置"
        verbose_name_plural = "审查配置"

    def __str__(self):
        return f"Config for {self.project.path_with_namespace}"


class AuditLog(TimeStampedModel):
    """操作审计日志"""

    class ActionType(models.TextChoices):
        CREATE = "create", "创建"
        UPDATE = "update", "更新"
        DELETE = "delete", "删除"
        LOGIN = "login", "登录"
        LOGOUT = "logout", "登出"
        REVIEW_START = "review_start", "开始审查"
        REVIEW_COMPLETE = "review_complete", "完成审查"
        CONFIG_CHANGE = "config_change", "配置变更"
        WEBHOOK_EVENT = "webhook_event", "Webhook 事件"

    # 用户
    user = models.ForeignKey(GitLabUser, on_delete=models.SET_NULL, null=True, blank=True, related_name="audit_logs")

    # 项目
    project = models.ForeignKey(GitLabProject, on_delete=models.SET_NULL, null=True, blank=True, related_name="audit_logs")

    # 操作
    action = models.CharField(max_length=50, choices=ActionType.choices, db_index=True)

    # 资源
    resource_type = models.CharField(max_length=50)  # project, pull_request, review_task, config
    resource_id = models.CharField(max_length=100)

    # 详情
    details = models.JSONField(default=dict, blank=True)

    # 请求信息
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    user_agent = models.CharField(max_length=500, null=True, blank=True)

    class Meta:
        db_table = "audit_logs"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["user", "-created_at"]),
            models.Index(fields=["project", "-created_at"]),
            models.Index(fields=["action", "-created_at"]),
            models.Index(fields=["resource_type", "resource_id"]),
        ]

    def __str__(self):
        return f"{self.action} - {self.resource_type}:{self.resource_id}"


class ReviewReport(TimeStampedModel):
    """审查报告 (持久化的审查结果)"""

    # 关联 PR
    pull_request = models.ForeignKey(PullRequest, on_delete=models.CASCADE, related_name="reports", db_index=True)

    # 报告类型
    review_type = models.CharField(max_length=20, choices=ReviewTask.ReviewType.choices)

    # 评分
    overall_score = models.IntegerField(null=True, blank=True, validators=[MinValueValidator(1), MaxValueValidator(10)])
    effort_estimate = models.CharField(max_length=50, null=True, blank=True)  # small, medium, large, x-large

    # 问题统计
    critical_issues = models.PositiveIntegerField(default=0)
    major_issues = models.PositiveIntegerField(default=0)
    minor_issues = models.PositiveIntegerField(default=0)
    suggestions = models.PositiveIntegerField(default=0)

    # 完整报告 (JSON)
    report_data = models.JSONField(default=dict)

    # 摘要
    summary = models.TextField(blank=True)

    class Meta:
        db_table = "review_reports"
        ordering = ["-created_at"]
        indexes = [
            models.Index(fields=["pull_request", "-created_at"]),
            models.Index(fields=["review_type", "-created_at"]),
        ]

    def __str__(self):
        return f"Report for {self.pull_request} - {self.review_type}"
