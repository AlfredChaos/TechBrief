from __future__ import annotations

from django.urls import path

from techbrief.apps.admin_console.views import (
    ContentActionPublishWebApiView,
    ContentActionRetryStageApiView,
    ContentDetailApiView,
    ContentDetailPageView,
    ContentListApiView,
    ContentListView,
    DashboardApiView,
    DashboardView,
    ManualIntakeApiView,
    ManualIntakePageView,
    ManualPublishApiView,
    ManualPublishPageView,
    PublishWebApiView,
    PublishWechatApiView,
    SourceDeleteApiView,
    SourceDetailApiView,
    SourceDetailPageView,
    SourceDiscoveryApiView,
    SourceListApiView,
    SourceListView,
    SourceToggleApiView,
    SubscriberListApiView,
    SubscriberListView,
    WorkflowRunDetailApiView,
    WorkflowRunListApiView,
    WorkflowRunRetryApiView,
    WorkflowListView,
)

app_name = "admin_console"

urlpatterns = [
    # Page views
    path("", DashboardView.as_view(), name="dashboard"),
    path("sources/", SourceListView.as_view(), name="sources"),
    path("sources/<uuid:source_id>/", SourceDetailPageView.as_view(), name="source-detail"),
    path("content/", ContentListView.as_view(), name="content"),
    path("content/<uuid:content_item_id>/", ContentDetailPageView.as_view(), name="content-detail"),
    path("subscribers/", SubscriberListView.as_view(), name="subscribers"),
    path("workflow/", WorkflowListView.as_view(), name="workflow"),
    path("manual-intake/", ManualIntakePageView.as_view(), name="manual-intake"),
    path("manual-publish/", ManualPublishPageView.as_view(), name="manual-publish"),
    # API endpoints
    path("api/dashboard/", DashboardApiView.as_view(), name="api-dashboard"),
    path("api/sources/", SourceListApiView.as_view(), name="api-sources"),
    path(
        "api/sources/<uuid:source_id>/",
        SourceDetailApiView.as_view(),
        name="api-source-detail",
    ),
    path(
        "api/sources/<uuid:source_id>/delete/",
        SourceDeleteApiView.as_view(),
        name="api-source-delete",
    ),
    path(
        "api/sources/<uuid:source_id>/toggle/",
        SourceToggleApiView.as_view(),
        name="api-source-toggle",
    ),
    path(
        "api/sources/<uuid:source_id>/discover/",
        SourceDiscoveryApiView.as_view(),
        name="api-source-discover",
    ),
    path("api/content-items/", ContentListApiView.as_view(), name="api-content"),
    path(
        "api/content-items/<uuid:content_item_id>/",
        ContentDetailApiView.as_view(),
        name="api-content-detail",
    ),
    path(
        "api/content-items/<uuid:content_item_id>/retry-stage/",
        ContentActionRetryStageApiView.as_view(),
        name="api-content-retry-stage",
    ),
    path(
        "api/content-items/<uuid:content_item_id>/publish-web/",
        ContentActionPublishWebApiView.as_view(),
        name="api-content-publish-web",
    ),
    path("api/subscribers/", SubscriberListApiView.as_view(), name="api-subscribers"),
    path("api/workflow/runs/", WorkflowRunListApiView.as_view(), name="api-workflow"),
    path(
        "api/workflow/runs/<uuid:run_id>/",
        WorkflowRunDetailApiView.as_view(),
        name="api-workflow-run-detail",
    ),
    path(
        "api/workflow/runs/<uuid:run_id>/retry/",
        WorkflowRunRetryApiView.as_view(),
        name="api-workflow-run-retry",
    ),
    path("api/manual-intake/", ManualIntakeApiView.as_view(), name="api-manual-intake"),
    path("api/publish/", ManualPublishApiView.as_view(), name="api-publish"),
    path("api/publish/web/", PublishWebApiView.as_view(), name="api-publish-web"),
    path("api/publish/wechat/", PublishWechatApiView.as_view(), name="api-publish-wechat"),
]
