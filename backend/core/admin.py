"""Django Admin 配置"""
from django.contrib import admin
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
    class CustomUserAdmin(admin.ModelAdmin):
        list_display = ["username", "email", "is_staff", "is_active", "date_joined"]
        list_filter = ["is_staff", "is_active", "groups"]
        search_fields = ["username", "email"]
        ordering = ["username"]
