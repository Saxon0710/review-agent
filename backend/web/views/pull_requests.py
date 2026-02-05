"""Django Views - Pull Requests"""
from django.views.generic import DetailView
from django.contrib.auth.mixins import LoginRequiredMixin
from django.shortcuts import get_object_or_404
from django.db.models import Count, Q, Avg
from core.models import PullRequest, ReviewTask, ReviewComment, GitLabProject


class MRDetailView(LoginRequiredMixin, DetailView):
    """MR 详情"""
    model = PullRequest
    template_name = "pull_requests/detail.html"
    context_object_name = "mr"

    def get_object(self):
        return get_object_or_404(
            PullRequest,
            project__path_with_namespace=self.kwargs["path"],
            mr_iid=self.kwargs["mr_iid"]
        )

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        mr = self.object
        project = mr.project

        # 审查任务历史
        context["review_tasks"] = ReviewTask.objects.filter(
            pull_request=mr
        ).order_by("-created_at")

        # 审查统计
        review_stats = ReviewTask.objects.filter(pull_request=mr).aggregate(
            total=Count("id"),
            completed=Count("id", filter=Q(status="completed")),
            failed=Count("id", filter=Q(status="failed")),
            avg_duration=Avg("duration_seconds", filter=Q(duration_seconds__isnull=False))
        )

        context["review_stats"] = review_stats

        # 最新审查
        latest_review = ReviewTask.objects.filter(
            pull_request=mr
        ).order_by("-created_at").first()
        context["latest_review"] = latest_review

        # 项目信息
        context["project"] = project

        return context
