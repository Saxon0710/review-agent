"""Django URL Configuration"""
from django.urls import path
from .views import dashboard, projects, pull_requests, reviews

app_name = "web"

urlpatterns = [
    # 仪表板
    path("", dashboard.DashboardView.as_view(), name="dashboard"),
    path("api/stats/", dashboard.dashboard_stats_api, name="dashboard_stats_api"),

    # 项目
    path("projects/", projects.ProjectListView.as_view(), name="project_list"),
    path("projects/<path:path>/", projects.ProjectDetailView.as_view(), name="project_detail"),
    path("projects/<int:project_id>/sync/", projects.sync_project, name="project_sync"),
    path("projects/<int:project_id>/api/stats/", dashboard.project_stats_api, name="project_stats_api"),
    path("projects/<int:project_id>/api/detail-stats/", projects.project_detail_stats_api, name="project_detail_stats_api"),

    # MR
    path("mr/<path:path>/<int:mr_iid>/", pull_requests.MRDetailView.as_view(), name="mr_detail"),
    path("mr/<path:path>/<int:mr_iid>/review/", projects.start_review, name="mr_review_start"),

    # 审查
    path("reviews/", reviews.ReviewListView.as_view(), name="review_list"),
    path("reviews/<uuid:task_id>/", reviews.ReviewDetailView.as_view(), name="review_detail"),
    path("reviews/<uuid:task_id>/cancel/", reviews.cancel_review, name="review_cancel"),
    path("reviews/api/stats/", dashboard.review_stats_api, name="review_stats_api"),
    path("reviews/api/list-stats/", reviews.review_list_stats_api, name="review_list_stats_api"),
]
