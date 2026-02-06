"""Django Admin 配置"""
from django.contrib import admin
from django.contrib.auth.admin import UserAdmin
from django.contrib.auth import get_user_model
from django.db.models import Count

from .models import (
    GitLabProject,
    GitLabUser,
    PullRequest,
    ReviewTask,
    ReviewComment,
    ReviewConfiguration,
    AuditLog,
    ReviewReport,
)

User = get_user_model()

# 设置 Admin 站点中文名称
admin.site.site_header = "Review Agent 管理后台"
admin.site.site_title = "Review Agent 管理"
admin.site.index_title = "欢迎使用 Review Agent 代码审查系统"


@admin.register(GitLabProject)
class GitLabProjectAdmin(admin.ModelAdmin):
    list_display = [
        "name",
        "path_with_namespace",
        "visibility",
        "is_active",
        "webhook_enabled",
        "mr_count",
        "review_count",
        "last_sync_at",
        "created_at",
    ]
    list_filter = ["visibility", "is_active", "webhook_enabled"]
    search_fields = ["name", "path_with_namespace"]
    readonly_fields = ["project_id", "created_at", "updated_at"]
    fieldsets = (
        ("基础信息", {
            "fields": ("project_id", "name", "path_with_namespace", "description", "visibility", "default_branch")
        }),
        ("URL", {
            "fields": ("url",)
        }),
        ("Webhook", {
            "fields": ("webhook_url", "webhook_secret", "webhook_enabled")
        }),
        ("状态", {
            "fields": ("is_active", "last_sync_at")
        }),
        ("配置", {
            "fields": ("settings",)
        }),
        ("统计", {
            "fields": ("mr_count", "review_count"),
        }),
    )

    def get_queryset(self, request):
        return super().get_queryset(request).annotate(
            mr_count_count=Count("pull_requests"),
            review_count_count=Count("pull_requests__review_tasks"),
        )


@admin.register(GitLabUser)
class GitLabUserAdmin(admin.ModelAdmin):
    list_display = [
        "gitlab_username",
        "user",
        "gitlab_email",
        "gitlab_user_id",
        "is_active",
        "last_login_at",
        "created_at",
    ]
    list_filter = ["is_active"]
    search_fields = ["gitlab_username", "gitlab_email", "user__username"]
    readonly_fields = ["gitlab_user_id", "created_at", "updated_at"]


@admin.register(PullRequest)
class PullRequestAdmin(admin.ModelAdmin):
    list_display = [
        "title",
        "project",
        "mr_iid",
        "state",
        "draft",
        "author",
        "source_branch",
        "target_branch",
        "additions",
        "deletions",
        "gitlab_created_at",
    ]
    list_filter = ["state", "draft", "project"]
    search_fields = ["title", "description"]
    readonly_fields = ["mr_id", "created_at", "updated_at"]
    date_hierarchy = "gitlab_created_at"


@admin.register(ReviewTask)
class ReviewTaskAdmin(admin.ModelAdmin):
    list_display = [
        "task_id",
        "pull_request",
        "review_type",
        "status",
        "triggered_by",
        "trigger_user",
        "ai_model",
        "duration_seconds",
        "tokens_used",
        "created_at",
        "started_at",
        "completed_at",
    ]
    list_filter = ["review_type", "status", "triggered_by"]
    search_fields = ["task_id", "pull_request__title"]
    readonly_fields = ["task_id", "created_at", "updated_at"]
    date_hierarchy = "created_at"

    def get_queryset(self, request):
        return super().get_queryset(request).select_related("pull_request__project", "trigger_user")


@admin.register(ReviewComment)
class ReviewCommentAdmin(admin.ModelAdmin):
    list_display = [
        "id",
        "task",
        "comment_type",
        "file_path",
        "line_start",
        "line_end",
        "is_published",
        "published_at",
        "created_at",
    ]
    list_filter = ["comment_type", "is_published"]
    search_fields = ["body", "file_path"]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(ReviewConfiguration)
class ReviewConfigurationAdmin(admin.ModelAdmin):
    list_display = [
        "project",
        "auto_review_on_open",
        "auto_review_on_push",
        "ignore_draft",
        "ai_model",
        "ai_temperature",
        "review_max_findings",
        "created_at",
    ]
    list_filter = [
        "auto_review_on_open",
        "auto_review_on_push",
        "ignore_draft",
        "review_require_tests",
        "review_require_security",
    ]
    readonly_fields = ["created_at", "updated_at"]


@admin.register(AuditLog)
class AuditLogAdmin(admin.ModelAdmin):
    list_display = [
        "created_at",
        "user",
        "project",
        "action",
        "resource_type",
        "resource_id",
        "ip_address",
    ]
    list_filter = ["action", "resource_type"]
    search_fields = ["user__gitlab_username", "resource_id"]
    readonly_fields = ["created_at", "updated_at"]
    date_hierarchy = "created_at"

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        return False

    def has_delete_permission(self, request, obj=None):
        return request.user.is_superuser


@admin.register(ReviewReport)
class ReviewReportAdmin(admin.ModelAdmin):
    list_display = [
        "pull_request",
        "review_type",
        "overall_score",
        "effort_estimate",
        "critical_issues",
        "major_issues",
        "minor_issues",
        "suggestions",
        "created_at",
    ]
    list_filter = ["review_type"]
    readonly_fields = ["created_at", "updated_at"]
    date_hierarchy = "created_at"


# 扩展 User Admin
if User.__name__ == "User":
    try:
        admin.site.unregister(User)
    except admin.sites.NotRegistered:
        pass

    @admin.register(User)
    class CustomUserAdmin(UserAdmin):
        list_display = ["username", "email", "is_staff", "is_active", "date_joined"]
        list_filter = ["is_staff", "is_active", "groups"]
        search_fields = ["username", "email"]
        ordering = ["username"]


# ========== Celery Beat 中文化 ==========
try:
    from django_celery_beat import models as beat_models

    # PeriodicTask - 周期任务
    try:
        admin.site.unregister(beat_models.PeriodicTask)
    except admin.sites.NotRegistered:
        pass

    @admin.register(beat_models.PeriodicTask)
    class PeriodicTaskAdmin(admin.ModelAdmin):
        list_display = ["name", "task", "enabled", "interval", "crontab"]
        list_filter = ["enabled", "task"]
        search_fields = ["name"]

        class Meta:
            verbose_name = "周期任务"
            verbose_name_plural = "周期任务"

    beat_models.PeriodicTask._meta.verbose_name = "周期任务"
    beat_models.PeriodicTask._meta.verbose_name_plural = "周期任务"

    # IntervalSchedule - 间隔调度
    try:
        admin.site.unregister(beat_models.IntervalSchedule)
    except admin.sites.NotRegistered:
        pass

    @admin.register(beat_models.IntervalSchedule)
    class IntervalScheduleAdmin(admin.ModelAdmin):
        list_display = ["every", "period"]

        class Meta:
            verbose_name = "间隔调度"
            verbose_name_plural = "间隔调度"

    beat_models.IntervalSchedule._meta.verbose_name = "间隔调度"
    beat_models.IntervalSchedule._meta.verbose_name_plural = "间隔调度"

    # CrontabSchedule - Crontab 调度
    try:
        admin.site.unregister(beat_models.CrontabSchedule)
    except admin.sites.NotRegistered:
        pass

    @admin.register(beat_models.CrontabSchedule)
    class CrontabScheduleAdmin(admin.ModelAdmin):
        list_display = ["minute", "hour", "day_of_week", "day_of_month", "month_of_year"]

        class Meta:
            verbose_name = "Crontab 调度"
            verbose_name_plural = "Crontab 调度"

    beat_models.CrontabSchedule._meta.verbose_name = "Crontab 调度"
    beat_models.CrontabSchedule._meta.verbose_name_plural = "Crontab 调度"

    # ClockedSchedule - 定时调度
    try:
        admin.site.unregister(beat_models.ClockedSchedule)
    except admin.sites.NotRegistered:
        pass

    @admin.register(beat_models.ClockedSchedule)
    class ClockedScheduleAdmin(admin.ModelAdmin):
        list_display = ["clocked_time"]

        class Meta:
            verbose_name = "定时调度"
            verbose_name_plural = "定时调度"

    beat_models.ClockedSchedule._meta.verbose_name = "定时调度"
    beat_models.ClockedSchedule._meta.verbose_name_plural = "定时调度"

    # SolarSchedule - 日照调度
    try:
        admin.site.unregister(beat_models.SolarSchedule)
    except admin.sites.NotRegistered:
        pass

    @admin.register(beat_models.SolarSchedule)
    class SolarScheduleAdmin(admin.ModelAdmin):
        list_display = ["event", "latitude", "longitude"]

        class Meta:
            verbose_name = "日照调度"
            verbose_name_plural = "日照调度"

    beat_models.SolarSchedule._meta.verbose_name = "日照调度"
    beat_models.SolarSchedule._meta.verbose_name_plural = "日照调度"

    # 修改应用名称
    beat_models.PeriodicTask._meta.app_config.verbose_name = "定时任务"

except ImportError:
    pass


# ========== Celery Results 中文化 ==========
try:
    from django_celery_results import models as result_models

    # TaskResult - 任务结果
    try:
        admin.site.unregister(result_models.TaskResult)
    except admin.sites.NotRegistered:
        pass

    @admin.register(result_models.TaskResult)
    class TaskResultAdmin(admin.ModelAdmin):
        list_display = ["task_id", "status", "date_created", "date_done"]
        list_filter = ["status"]
        search_fields = ["task_id"]
        readonly_fields = ["date_created", "date_done"]

        class Meta:
            verbose_name = "任务结果"
            verbose_name_plural = "任务结果"

    result_models.TaskResult._meta.verbose_name = "任务结果"
    result_models.TaskResult._meta.verbose_name_plural = "任务结果"

    # 修改应用名称
    if hasattr(result_models.TaskResult._meta, 'app_config'):
        result_models.TaskResult._meta.app_config.verbose_name = "任务结果"

except ImportError:
    pass


# ========== 修改 Auth 应用中文名称 ==========
try:
    from django.contrib.auth.models import Group
    try:
        admin.site.unregister(Group)
    except admin.sites.NotRegistered:
        pass

    @admin.register(Group)
    class GroupAdmin(admin.ModelAdmin):
        list_display = ["name"]
        search_fields = ["name"]

    Group._meta.verbose_name = "用户组"
    Group._meta.verbose_name_plural = "用户组"
except Exception:
    pass
