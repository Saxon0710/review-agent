"""Django Views - Reviews"""
from django.views.generic import ListView, DetailView, FormView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.contrib import messages
from django.db.models import Count, Q, Avg, Sum, F
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from django.utils import timezone
from datetime import datetime, timedelta
from core.models import (
    ReviewTask,
    PullRequest,
    GitLabProject,
    ReviewComment,
    GitLabUser,
    ReviewReport,
)


class ReviewListView(LoginRequiredMixin, ListView):
    """审查任务列表"""
    model = ReviewTask
    template_name = "reviews/list.html"
    context_object_name = "tasks"
    paginate_by = 20

    def get_queryset(self):
        queryset = ReviewTask.objects.select_related(
            "pull_request__project",
            "pull_request__author",
        ).order_by("-created_at")

        # 筛选条件
        project_id = self.request.GET.get("project")
        project_name = self.request.GET.get("project_name")
        review_type = self.request.GET.get("type")
        status = self.request.GET.get("status")
        trigger = self.request.GET.get("trigger")
        developer_name = self.request.GET.get("developer")
        date_from = self.request.GET.get("date_from")
        date_to = self.request.GET.get("date_to")

        # 项目筛选
        if project_id:
            queryset = queryset.filter(pull_request__project_id=project_id)
        elif project_name:
            queryset = queryset.filter(pull_request__project__name__icontains=project_name)

        # 审查类型筛选
        if review_type:
            queryset = queryset.filter(review_type=review_type)

        # 状态筛选
        if status:
            queryset = queryset.filter(status=status)

        # 触发方式筛选
        if trigger:
            queryset = queryset.filter(triggered_by=trigger)

        # 开发者筛选 (通过 MR 作者)
        if developer_name:
            queryset = queryset.filter(
                Q(pull_request__author__gitlab_username__icontains=developer_name) |
                Q(pull_request__author__gitlab_email__icontains=developer_name)
            )

        # 时间范围筛选
        if date_from:
            try:
                date_from_obj = datetime.strptime(date_from, "%Y-%m-%d").date()
                queryset = queryset.filter(created_at__date__gte=date_from_obj)
            except ValueError:
                pass

        if date_to:
            try:
                date_to_obj = datetime.strptime(date_to, "%Y-%m-%d").date()
                # 包含结束日期的整天
                date_to_obj = timezone.make_aware(datetime.combine(date_to_obj, datetime.max.time()))
                queryset = queryset.filter(created_at__lte=date_to_obj)
            except ValueError:
                pass

        return queryset

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)

        # 获取所有项目用于筛选
        context["projects"] = GitLabProject.objects.filter(is_active=True)

        # 统计数据 - 使用相同的筛选条件
        base_queryset = self._get_filtered_queryset()

        stats = base_queryset.aggregate(
            total=Count("id"),
            pending=Count("id", filter=Q(status="pending")),
            running=Count("id", filter=Q(status="running")),
            completed=Count("id", filter=Q(status="completed")),
            failed=Count("id", filter=Q(status="failed")),
            avg_duration=Avg("duration_seconds", filter=Q(duration_seconds__isnull=False))
        )

        context["stats"] = stats

        # 保存筛选参数用于模板回填
        context["filters"] = {
            "project": self.request.GET.get("project", ""),
            "project_name": self.request.GET.get("project_name", ""),
            "type": self.request.GET.get("type", ""),
            "status": self.request.GET.get("status", ""),
            "trigger": self.request.GET.get("trigger", ""),
            "developer": self.request.GET.get("developer", ""),
            "date_from": self.request.GET.get("date_from", ""),
            "date_to": self.request.GET.get("date_to", ""),
        }

        return context

    def _get_filtered_queryset(self):
        """获取应用筛选后的查询集（用于统计）"""
        queryset = ReviewTask.objects.all()

        project_id = self.request.GET.get("project")
        project_name = self.request.GET.get("project_name")
        review_type = self.request.GET.get("type")
        status = self.request.GET.get("status")
        trigger = self.request.GET.get("trigger")
        developer_name = self.request.GET.get("developer")
        date_from = self.request.GET.get("date_from")
        date_to = self.request.GET.get("date_to")

        if project_id:
            queryset = queryset.filter(pull_request__project_id=project_id)
        elif project_name:
            queryset = queryset.filter(pull_request__project__name__icontains=project_name)

        if review_type:
            queryset = queryset.filter(review_type=review_type)

        if status:
            queryset = queryset.filter(status=status)

        if trigger:
            queryset = queryset.filter(triggered_by=trigger)

        if developer_name:
            queryset = queryset.filter(
                Q(pull_request__author__gitlab_username__icontains=developer_name) |
                Q(pull_request__author__gitlab_email__icontains=developer_name)
            )

        if date_from:
            try:
                date_from_obj = datetime.strptime(date_from, "%Y-%m-%d").date()
                queryset = queryset.filter(created_at__date__gte=date_from_obj)
            except ValueError:
                pass

        if date_to:
            try:
                date_to_obj = datetime.strptime(date_to, "%Y-%m-%d").date()
                date_to_obj = timezone.make_aware(datetime.combine(date_to_obj, datetime.max.time()))
                queryset = queryset.filter(created_at__lte=date_to_obj)
            except ValueError:
                pass

        return queryset


class ReviewDetailView(LoginRequiredMixin, DetailView):
    """审查任务详情"""
    model = ReviewTask
    template_name = "reviews/detail.html"
    context_object_name = "task"
    slug_field = "task_id"
    slug_url_kwarg = "task_id"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        task = self.object

        # 获取关联的评论
        context["comments"] = ReviewComment.objects.filter(
            review_task=task
        ).order_by("file_path", "line_number")

        return context


def cancel_review(request, task_id):
    """取消审查任务"""
    task = get_object_or_404(ReviewTask, task_id=task_id)

    if task.status in ["pending", "running"]:
        # TODO: 调用 FastAPI 取消接口
        task.status = "cancelled"
        task.save()
        messages.success(request, "任务已取消")
    else:
        messages.warning(request, f"任务状态为 {task.get_status_display()}，无法取消")

    return redirect("web:review_detail", task_id=task_id)


@require_GET
def review_list_stats_api(request):
    """
    审查列表统计 API
    用于前端图表动态加载
    """
    # 获取筛选参数
    project_id = request.GET.get("project")
    project_name = request.GET.get("project_name")
    review_type = request.GET.get("type")
    status = request.GET.get("status")
    trigger = request.GET.get("trigger")
    developer_name = request.GET.get("developer")
    date_from = request.GET.get("date_from")
    date_to = request.GET.get("date_to")

    # 构建查询
    queryset = ReviewTask.objects.select_related(
        "pull_request__project",
        "pull_request__author",
    )

    if project_id:
        queryset = queryset.filter(pull_request__project_id=project_id)
    elif project_name:
        queryset = queryset.filter(pull_request__project__name__icontains=project_name)

    if review_type:
        queryset = queryset.filter(review_type=review_type)

    if status:
        queryset = queryset.filter(status=status)

    if trigger:
        queryset = queryset.filter(triggered_by=trigger)

    if developer_name:
        queryset = queryset.filter(
            Q(pull_request__author__gitlab_username__icontains=developer_name) |
            Q(pull_request__author__gitlab_email__icontains=developer_name)
        )

    if date_from:
        try:
            date_from_obj = datetime.strptime(date_from, "%Y-%m-%d").date()
            queryset = queryset.filter(created_at__date__gte=date_from_obj)
        except ValueError:
            pass

    if date_to:
        try:
            date_to_obj = datetime.strptime(date_to, "%Y-%m-%d").date()
            date_to_obj = timezone.make_aware(datetime.combine(date_to_obj, datetime.max.time()))
            queryset = queryset.filter(created_at__lte=date_to_obj)
        except ValueError:
            pass

    # 按类型统计
    by_type = (
        queryset.values("review_type")
        .annotate(total=Count("id"))
        .order_by("-total")
    )

    # 按状态统计
    by_status = (
        queryset.values("status")
        .annotate(count=Count("id"))
        .order_by("-count")
    )

    # 按触发方式统计
    by_trigger = (
        queryset.values("triggered_by")
        .annotate(total=Count("id"))
        .order_by("-total")
    )

    # 时间趋势 (最近30天)
    now = timezone.now()
    thirty_days_ago = now - timedelta(days=30)

    trends = (
        queryset.filter(created_at__gte=thirty_days_ago)
        .annotate(date=timezone.now().date())  # 简化
        .values("created_at__date")
        .annotate(
            total=Count("id"),
            completed=Count("id", filter=Q(status="completed")),
            failed=Count("id", filter=Q(status="failed")),
        )
        .order_by("created_at__date")
    )

    data = {
        "by_type": list(by_type),
        "by_status": list(by_status),
        "by_trigger": list(by_trigger),
        "trends": [
            {
                "date": str(t["created_at__date"]),
                "total": t["total"],
                "completed": t["completed"],
                "failed": t["failed"],
            }
            for t in trends
        ],
    }

    return JsonResponse(data)
