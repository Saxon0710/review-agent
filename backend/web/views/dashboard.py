"""Django Views - Dashboard"""
from django.views.generic import TemplateView
from django.contrib.auth.mixins import LoginRequiredMixin
from core.models import (
    GitLabProject,
    PullRequest,
    ReviewTask,
    ReviewReport,
    ReviewComment,
    GitLabUser,
)
from django.db.models import Count, Q, Avg, Sum, F, Value as V
from django.db.models.functions import TruncDate, TruncDay, TruncWeek, TruncMonth
from datetime import timedelta, datetime
from django.utils import timezone
from django.http import JsonResponse
from django.views.decorators.http import require_GET
import json


class DashboardView(LoginRequiredMixin, TemplateView):
    """仪表板视图"""
    template_name = "dashboard.html"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        now = timezone.now()
        last_7_days = now - timedelta(days=7)
        last_30_days = now - timedelta(days=30)

        # ========== 基础统计卡片 ==========
        context["stats"] = {
            "total_projects": GitLabProject.objects.filter(is_active=True).count(),
            "total_mrs": PullRequest.objects.count(),
            "total_reviews": ReviewTask.objects.count(),
            "completed_reviews": ReviewTask.objects.filter(status="completed").count(),
            "recent_reviews": ReviewTask.objects.filter(
                status="completed",
                completed_at__gte=last_7_days
            ).count(),
        }

        # ========== 状态分布 ==========
        status_stats = ReviewTask.objects.values("status").annotate(
            count=Count("id")
        ).order_by("status")
        context["status_stats"] = {s["status"]: s["count"] for s in status_stats}

        # ========== 审查类型分布 ==========
        type_stats = ReviewTask.objects.values("review_type").annotate(
            count=Count("id")
        ).order_by("-count")
        context["type_stats"] = {t["review_type"]: t["count"] for t in type_stats}

        # ========== 最近30天趋势数据 (用于图表) ==========
        daily_trends = (
            ReviewTask.objects
            .filter(created_at__gte=last_30_days)
            .annotate(date=TruncDate("created_at"))
            .values("date")
            .annotate(
                total=Count("id"),
                completed=Count("id", filter=Q(status="completed")),
                failed=Count("id", filter=Q(status="failed")),
            )
            .order_by("date")
        )
        context["daily_trends"] = list(daily_trends)

        # ========== 按周统计趋势 ==========
        weekly_trends = (
            ReviewTask.objects
            .filter(created_at__gte=last_30_days)
            .annotate(week=TruncWeek("created_at"))
            .values("week")
            .annotate(
                total=Count("id"),
                completed=Count("id", filter=Q(status="completed")),
                avg_duration=Avg("duration_seconds", filter=Q(duration_seconds__isnull=False)),
            )
            .order_by("week")
        )
        context["weekly_trends"] = [
            {
                "week": w["week"].strftime("%Y-%m-%d") if w["week"] else "",
                "total": w["total"],
                "completed": w["completed"],
                "avg_duration": round(w["avg_duration"] or 0, 2),
            }
            for w in weekly_trends
        ]

        # ========== 项目活跃度排行 (Top 10) ==========
        top_projects = (
            GitLabProject.objects
            .filter(is_active=True)
            .annotate(
                mr_count=Count("pull_requests", distinct=True),
                review_count=Count("pull_requests__review_tasks", distinct=True),
            )
            .order_by("-review_count")[:10]
        )
        context["top_projects"] = list(top_projects)

        # ========== 开发者活跃度排行 (Top 10) ==========
        top_users = (
            GitLabUser.objects
            .annotate(
                mr_count=Count("authored_mrs"),
                review_count=Count("authored_mrs__review_tasks"),
            )
            .filter(review_count__gt=0)
            .order_by("-review_count")[:10]
        )
        context["top_users"] = list(top_users)

        # ========== 审查触发方式分布 ==========
        trigger_stats = ReviewTask.objects.values("triggered_by").annotate(
            count=Count("id")
        ).order_by("-count")
        context["trigger_stats"] = {t["triggered_by"]: t["count"] for t in trigger_stats}

        # ========== 最近7天的每日审查数量 ==========
        daily_counts = []
        for i in range(7):
            date = (now - timedelta(days=6-i)).date()
            count = ReviewTask.objects.filter(
                created_at__date=date
            ).count()
            completed_count = ReviewTask.objects.filter(
                completed_at__date=date,
                status="completed"
            ).count()
            daily_counts.append({
                "date": date.strftime("%Y-%m-%d"),
                "created": count,
                "completed": completed_count,
            })
        context["daily_counts"] = daily_counts

        # ========== 评论统计 (最近30天) ==========
        comment_stats = ReviewComment.objects.filter(
            created_at__gte=last_30_days
        ).aggregate(
            total=Count("id"),
            by_type=Count("comment_type"),
            avg_per_review=Avg("review_task__comments__id"),
        )
        context["comment_stats"] = comment_stats

        # ========== 评论类型分布 ==========
        comment_type_stats = (
            ReviewComment.objects
            .filter(created_at__gte=last_30_days)
            .values("comment_type")
            .annotate(count=Count("id"))
            .order_by("-count")
        )
        context["comment_type_stats"] = list(comment_type_stats)

        # ========== 最近的审查任务 ==========
        context["recent_tasks"] = list(
            ReviewTask.objects
            .select_related("pull_request__project")
            .order_by("-created_at")[:10]
        )

        # ========== 最近的 MR ==========
        context["recent_mrs"] = list(
            PullRequest.objects
            .select_related("project")
            .order_by("-gitlab_created_at")[:10]
        )

        # ========== 问题统计 (基于 ReviewComment) ==========
        issue_stats = (
            ReviewComment.objects
            .filter(review_task__status="completed")
            .values("review_task__pull_request__project__name")
            .annotate(
                total_comments=Count("id"),
                file_comments=Count("id", filter=Q(comment_type="file")),
                line_comments=Count("id", filter=Q(comment_type="line")),
            )
            .order_by("-total_comments")[:10]
        )
        context["issue_stats"] = list(issue_stats)

        # ========== 审查完成率趋势 ==========
        completion_rates = []
        for i in range(4):
            week_start = now - timedelta(weeks=i+1)
            week_end = now - timedelta(weeks=i)
            total = ReviewTask.objects.filter(
                created_at__gte=week_start,
                created_at__lt=week_end,
            ).count()
            completed = ReviewTask.objects.filter(
                created_at__gte=week_start,
                created_at__lt=week_end,
                status="completed",
            ).count()
            rate = (completed / total * 100) if total > 0 else 0
            completion_rates.append({
                "week": f"周{4-i}",
                "rate": round(rate, 2),
                "total": total,
                "completed": completed,
            })
        completion_rates.reverse()
        context["completion_rates"] = completion_rates

        return context


@require_GET
def dashboard_stats_api(request):
    """
    仪表板统计数据 API
    用于前端图表动态加载
    """
    now = timezone.now()
    days = int(request.GET.get("days", 30))
    since = now - timedelta(days=days)

    # 时间范围数据
    trends = (
        ReviewTask.objects
        .filter(created_at__gte=since)
        .annotate(date=TruncDate("created_at"))
        .values("date")
        .annotate(
            total=Count("id"),
            completed=Count("id", filter=Q(status="completed")),
            failed=Count("id", filter=Q(status="failed")),
            running=Count("id", filter=Q(status="running")),
        )
        .order_by("date")
    )

    data = {
        "trends": [
            {
                "date": t["date"].strftime("%Y-%m-%d") if t["date"] else "",
                "total": t["total"],
                "completed": t["completed"],
                "failed": t["failed"],
                "running": t["running"],
            }
            for t in trends
        ],
        "summary": ReviewTask.objects.filter(created_at__gte=since).aggregate(
            total=Count("id"),
            completed=Count("id", filter=Q(status="completed")),
            failed=Count("id", filter=Q(status="failed")),
            avg_duration=Avg("duration_seconds", filter=Q(duration_seconds__isnull=False)),
        ),
    }

    return JsonResponse(data)


@require_GET
def project_stats_api(request, project_id):
    """
    项目统计数据 API
    """
    project = GitLabProject.objects.get(id=project_id)
    now = timezone.now()
    days = int(request.GET.get("days", 30))
    since = now - timedelta(days=days)

    # MR 状态趋势
    mr_trends = (
        PullRequest.objects
        .filter(project=project, gitlab_created_at__gte=since)
        .annotate(date=TruncDate("gitlab_created_at"))
        .values("date")
        .annotate(
            total=Count("id"),
            opened=Count("id", filter=Q(state="opened")),
            merged=Count("id", filter=Q(state="merged")),
            closed=Count("id", filter=Q(state="closed")),
        )
        .order_by("date")
    )

    # 审查趋势
    review_trends = (
        ReviewTask.objects
        .filter(pull_request__project=project, created_at__gte=since)
        .annotate(date=TruncDate("created_at"))
        .values("date")
        .annotate(
            total=Count("id"),
            completed=Count("id", filter=Q(status="completed")),
            avg_duration=Avg("duration_seconds", filter=Q(duration_seconds__isnull=False)),
        )
        .order_by("date")
    )

    data = {
        "mr_trends": [
            {
                "date": m["date"].strftime("%Y-%m-%d") if m["date"] else "",
                "total": m["total"],
                "opened": m["opened"],
                "merged": m["merged"],
                "closed": m["closed"],
            }
            for m in mr_trends
        ],
        "review_trends": [
            {
                "date": r["date"].strftime("%Y-%m-%d") if r["date"] else "",
                "total": r["total"],
                "completed": r["completed"],
                "avg_duration": round(r["avg_duration"] or 0, 2),
            }
            for r in review_trends
        ],
    }

    return JsonResponse(data)


@require_GET
def review_stats_api(request):
    """
    审查统计 API
    """
    now = timezone.now()
    days = int(request.GET.get("days", 30))
    since = now - timedelta(days=days)

    # 按类型统计
    by_type = (
        ReviewTask.objects
        .filter(created_at__gte=since)
        .values("review_type")
        .annotate(
            total=Count("id"),
            completed=Count("id", filter=Q(status="completed")),
            failed=Count("id", filter=Q(status="failed")),
            avg_duration=Avg("duration_seconds", filter=Q(duration_seconds__isnull=False)),
        )
        .order_by("-total")
    )

    # 按状态统计
    by_status = (
        ReviewTask.objects
        .filter(created_at__gte=since)
        .values("status")
        .annotate(count=Count("id"))
        .order_by("-count")
    )

    # 按触发方式统计
    by_trigger = (
        ReviewTask.objects
        .filter(created_at__gte=since)
        .values("triggered_by")
        .annotate(
            total=Count("id"),
            completed=Count("id", filter=Q(status="completed")),
        )
        .order_by("-total")
    )

    # 时间趋势
    trends = (
        ReviewTask.objects
        .filter(created_at__gte=since)
        .annotate(date=TruncDate("created_at"))
        .values("date")
        .annotate(
            total=Count("id"),
            completed=Count("id", filter=Q(status="completed")),
            failed=Count("id", filter=Q(status="failed")),
        )
        .order_by("date")
    )

    data = {
        "by_type": list(by_type),
        "by_status": list(by_status),
        "by_trigger": list(by_trigger),
        "trends": [
            {
                "date": t["date"].strftime("%Y-%m-%d") if t["date"] else "",
                "total": t["total"],
                "completed": t["completed"],
                "failed": t["failed"],
            }
            for t in trends
        ],
    }

    return JsonResponse(data)
