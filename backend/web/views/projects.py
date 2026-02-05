"""Django Views - Projects"""
from django.views.generic import ListView, DetailView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404, redirect
from django.urls import reverse
from django.contrib import messages
from django.http import JsonResponse
from django.views.decorators.http import require_GET
from django.db.models import Count, Q, Avg, Sum, F
from django.utils import timezone
from datetime import timedelta
from core.models import (
    GitLabProject,
    PullRequest,
    ReviewTask,
    ReviewConfiguration,
    ReviewReport,
    GitLabUser,
)


class ProjectListView(LoginRequiredMixin, ListView):
    """项目列表"""
    model = GitLabProject
    template_name = "projects/list.html"
    context_object_name = "projects"
    paginate_by = 20

    def get_queryset(self):
        return GitLabProject.objects.filter(is_active=True).select_related("config").annotate(
            mr_count=Count("pull_requests", distinct=True),
            review_count=Count("pull_requests__review_tasks", distinct=True),
        )


class ProjectDetailView(LoginRequiredMixin, DetailView):
    """项目详情"""
    model = GitLabProject
    template_name = "projects/detail.html"
    context_object_name = "project"
    slug_field = "path_with_namespace"
    slug_url_kwarg = "path"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        project = self.object

        # 筛选参数
        developer_filter = self.request.GET.get("developer", "")

        # 构建 MR 查询基础
        mr_queryset = PullRequest.objects.filter(project=project)
        if developer_filter:
            mr_queryset = mr_queryset.filter(
                Q(author__gitlab_username__icontains=developer_filter) |
                Q(author__gitlab_email__icontains=developer_filter)
            )

        # MR 列表
        context["merge_requests"] = mr_queryset.select_related("author").order_by("-gitlab_created_at")[:20]

        # 审查任务
        task_queryset = ReviewTask.objects.filter(pull_request__project=project)
        if developer_filter:
            task_queryset = task_queryset.filter(
                Q(pull_request__author__gitlab_username__icontains=developer_filter) |
                Q(pull_request__author__gitlab_email__icontains=developer_filter)
            )
        context["recent_tasks"] = task_queryset.select_related("pull_request").order_by("-created_at")[:20]

        # MR 统计
        mr_stats = mr_queryset.aggregate(
            total=Count("id"),
            opened=Count("id", filter=Q(state="opened")),
            merged=Count("id", filter=Q(state="merged")),
            closed=Count("id", filter=Q(state="closed")),
        )

        # 审查统计
        review_stats = task_queryset.aggregate(
            total=Count("id"),
            completed=Count("id", filter=Q(status="completed")),
            failed=Count("id", filter=Q(status="failed")),
        )

        context["stats"] = {
            "mr": mr_stats,
            "review": review_stats,
        }

        # 获取或创建配置
        config, created = ReviewConfiguration.objects.get_or_create(project=project)
        context["config"] = config

        # ========== 项目提交统计 ==========
        # 按月统计 MR 提交趋势 (最近12个月)
        twelve_months_ago = timezone.now() - timedelta(days=365)
        monthly_submissions = (
            mr_queryset.filter(gitlab_created_at__gte=twelve_months_ago)
            .values("gitlab_created_at__year", "gitlab_created_at__month")
            .annotate(count=Count("id"))
            .order_by("gitlab_created_at__year", "gitlab_created_at__month")
        )
        context["monthly_submissions"] = list(monthly_submissions)

        # 按开发者统计提交数
        developer_submissions = (
            mr_queryset.values("author__gitlab_username")
            .annotate(
                user_id=F("author__id"),
                total_mrs=Count("id"),
                merged_mrs=Count("id", filter=Q(state="merged")),
            )
            .exclude(author__gitlab_username__isnull=True)
            .order_by("-total_mrs")[:20]
        )
        context["developer_submissions"] = list(developer_submissions)

        # ========== 项目平均得分 ==========
        # 从 ReviewReport 获取平均得分
        avg_scores = ReviewReport.objects.filter(
            pull_request__project=project
        ).aggregate(
            avg_score=Avg("overall_score"),
            total_reports=Count("id"),
            avg_critical=Avg("critical_issues"),
            avg_major=Avg("major_issues"),
            avg_minor=Avg("minor_issues"),
        )
        context["avg_scores"] = avg_scores

        # 按月份统计平均得分
        monthly_scores = (
            ReviewReport.objects
            .filter(pull_request__project=project, created_at__gte=twelve_months_ago)
            .values("created_at__year", "created_at__month")
            .annotate(
                avg_score=Avg("overall_score"),
                count=Count("id"),
            )
            .order_by("created_at__year", "created_at__month")
        )
        context["monthly_scores"] = list(monthly_scores)

        # ========== 开发者统计 ==========
        # 开发者提交统计 (用于柱状图)
        developer_stats = (
            GitLabUser.objects
            .filter(authored_mrs__project=project)
            .annotate(
                total_mrs=Count("authored_mrs"),
                merged_mrs=Count("authored_mrs", filter=Q(authored_mrs__state="merged")),
                total_reviews=Count("authored_mrs__review_tasks"),
                completed_reviews=Count("authored_mrs__review_tasks", filter=Q(authored_mrs__review_tasks__status="completed")),
            )
            .filter(total_mrs__gt=0)
            .order_by("-total_mrs")[:20]
        )
        context["developer_stats"] = list(developer_stats)

        # 开发者平均得分
        developer_avg_scores = (
            ReviewReport.objects
            .filter(pull_request__project=project)
            .values("pull_request__author__gitlab_username")
            .annotate(
                user_id=F("pull_request__author__id"),
                author_name=F("pull_request__author__gitlab_username"),
                avg_score=Avg("overall_score"),
                total_reports=Count("id"),
                avg_critical=Avg("critical_issues"),
                avg_major=Avg("major_issues"),
            )
            .exclude(author_name__isnull=True)
            .exclude(avg_score__isnull=True)
            .order_by("-avg_score")[:20]
        )
        context["developer_avg_scores"] = list(developer_avg_scores)

        # 保存筛选参数
        context["filters"] = {
            "developer": developer_filter,
        }

        return context


def sync_project(request, project_id):
    """同步项目数据"""
    project = get_object_or_404(GitLabProject, id=project_id)

    # TODO: 实现同步逻辑 - 调用 GitLab 集成模块
    messages.info(request, f"正在同步项目 {project.name}...")

    return redirect("web:project_detail", path=project.path_with_namespace)


def start_review(request, path, mr_iid):
    """手动触发 MR 审查"""
    project = get_object_or_404(GitLabProject, path_with_namespace=path)
    mr = get_object_or_404(PullRequest, project=project, mr_iid=mr_iid)

    review_type = request.POST.get("review_type", "review")

    # TODO: 调用 FastAPI 审查接口
    messages.success(request, f"已提交 {mr.title} 的审查请求")

    return redirect("web:mr_detail", path=path, mr_iid=mr_iid)


@require_GET
def project_detail_stats_api(request, project_id):
    """
    项目详情统计 API
    用于前端图表动态加载
    """
    project = get_object_or_404(GitLabProject, id=project_id)
    developer_filter = request.GET.get("developer", "")

    # 构建 MR 查询
    mr_queryset = PullRequest.objects.filter(project=project)
    if developer_filter:
        mr_queryset = mr_queryset.filter(
            Q(author__gitlab_username__icontains=developer_filter) |
            Q(author__gitlab_email__icontains=developer_filter)
        )

    # 构建审查任务查询
    task_queryset = ReviewTask.objects.filter(pull_request__project=project)
    if developer_filter:
        task_queryset = task_queryset.filter(
            Q(pull_request__author__gitlab_username__icontains=developer_filter) |
            Q(pull_request__author__gitlab_email__icontains=developer_filter)
        )

    # 项目活动趋势 (最近30天，按天统计)
    thirty_days_ago = timezone.now() - timedelta(days=30)
    review_trends = []
    for i in range(30):
        date = thirty_days_ago + timedelta(days=i)
        date_end = date + timedelta(days=1)

        mr_count = mr_queryset.filter(
            gitlab_created_at__gte=date,
            gitlab_created_at__lt=date_end
        ).count()

        completed_count = task_queryset.filter(
            created_at__gte=date,
            created_at__lt=date_end,
            status="completed"
        ).count()

        review_trends.append({
            "date": date.isoformat(),
            "total": mr_count,
            "completed": completed_count
        })

    review_trends.reverse()  # 按时间正序排列

    # 项目提交统计 - 按月
    twelve_months_ago = timezone.now() - timedelta(days=365)
    monthly_submissions = (
        mr_queryset.filter(gitlab_created_at__gte=twelve_months_ago)
        .values("gitlab_created_at__year", "gitlab_created_at__month")
        .annotate(
            count=Count("id"),
            merged=Count("id", filter=Q(state="merged")),
        )
        .order_by("gitlab_created_at__year", "gitlab_created_at__month")
    )

    # 项目平均得分趋势
    monthly_scores = (
        ReviewReport.objects
        .filter(pull_request__project=project, created_at__gte=twelve_months_ago)
        .values("created_at__year", "created_at__month")
        .annotate(
            avg_score=Avg("overall_score"),
            count=Count("id"),
        )
        .order_by("created_at__year", "created_at__month")
    )

    # 开发者提交统计
    developer_submissions = (
        mr_queryset.values("author__gitlab_username", "author__id")
        .annotate(
            total_mrs=Count("id"),
            merged_mrs=Count("id", filter=Q(state="merged")),
            closed_mrs=Count("id", filter=Q(state="closed")),
        )
        .exclude(author__gitlab_username__isnull=True)
        .order_by("-total_mrs")[:20]
    )

    # 开发者平均得分
    developer_scores = (
        ReviewReport.objects
        .filter(pull_request__project=project)
        .values("pull_request__author__gitlab_username", "pull_request__author__id")
        .annotate(
            avg_score=Avg("overall_score"),
            total_reports=Count("id"),
            avg_critical=Avg("critical_issues"),
            avg_major=Avg("major_issues"),
        )
        .exclude(pull_request__author__gitlab_username__isnull=True)
        .exclude(avg_score__isnull=True)
        .order_by("-avg_score")[:20]
    )

    data = {
        "review_trends": review_trends,
        "monthly_submissions": [
            {
                "month": f"{m['gitlab_created_at__year']}-{m['gitlab_created_at__month']:02d}",
                "count": m["count"],
                "merged": m["merged"],
            }
            for m in monthly_submissions
        ],
        "monthly_scores": [
            {
                "month": f"{m['created_at__year']}-{m['created_at__month']:02d}",
                "avg_score": round(m["avg_score"], 2) if m["avg_score"] else 0,
                "count": m["count"],
            }
            for m in monthly_scores
        ],
        "developer_submissions": [
            {
                "username": d["author__gitlab_username"],
                "total_mrs": d["total_mrs"],
                "merged_mrs": d["merged_mrs"],
                "closed_mrs": d["closed_mrs"],
            }
            for d in developer_submissions
        ],
        "developer_scores": [
            {
                "username": d["pull_request__author__gitlab_username"],
                "avg_score": round(d["avg_score"], 2) if d["avg_score"] else 0,
                "total_reports": d["total_reports"],
                "avg_critical": round(d["avg_critical"], 2) if d["avg_critical"] else 0,
                "avg_major": round(d["avg_major"], 2) if d["avg_major"] else 0,
            }
            for d in developer_scores
        ],
    }

    return JsonResponse(data)
