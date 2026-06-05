from __future__ import annotations

from django.contrib.auth.mixins import LoginRequiredMixin, UserPassesTestMixin
from django.http import JsonResponse
from django.urls import reverse_lazy
from django.views import View
from django.views.generic import TemplateView

from techbrief.api.responses import error_payload, success_response
from techbrief.apps.admin_console.services import (
    AdminActionError,
    build_navigation,
    create_manual_content,
    create_source,
    create_wechat_draft_from_payload,
    delete_source,
    get_content_detail_data,
    get_content_detail_page_context,
    get_content_list_data,
    get_content_page_context,
    get_dashboard_data,
    get_dashboard_page_context,
    get_manual_publish_page_context,
    get_source_detail_data,
    get_source_list_data,
    get_source_page_context,
    get_subscriber_list_data,
    get_subscriber_page_context,
    get_workflow_page_context,
    get_workflow_run_list_data,
    get_workflow_run_timeline,
    publish_content_web,
    queue_manual_url_import,
    retry_content_stage,
    retry_wechat_publish_record,
    retry_workflow_run_stage,
    trigger_discovery,
    update_source_configuration,
)
from techbrief.apps.web.theme import build_theme_css_variables


class AdminAccessMixin(LoginRequiredMixin, UserPassesTestMixin):
    login_url = reverse_lazy("wagtailadmin_login")
    redirect_field_name = "next"
    active_nav = "dashboard"
    page_title = "TechBrief"
    page_subtitle = "Operator workspace"
    header_icon = "home"

    def test_func(self):
        user = self.request.user
        return user.is_authenticated and user.is_active and user.is_staff

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(
            {
                "page_title": self.page_title,
                "header_title": self.page_title,
                "page_subtitle": self.page_subtitle,
                "header_icon": self.header_icon,
                "nav_items": build_navigation(self.active_nav),
                "theme_css_variables": build_theme_css_variables(),
            }
        )
        return context


class DashboardView(AdminAccessMixin, TemplateView):
    template_name = "admin_console/dashboard.html"
    active_nav = "dashboard"
    page_title = "Admin Dashboard"
    page_subtitle = "Daily operational summary"
    header_icon = "home"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(get_dashboard_page_context())
        return context


class ContentListView(AdminAccessMixin, TemplateView):
    template_name = "admin_console/content_list.html"
    active_nav = "content"
    page_title = "Content Queue"
    page_subtitle = "Search and inspect staged content items"
    header_icon = "doc-full-inverse"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(get_content_page_context(self.request.GET))
        return context


class SubscriberListView(AdminAccessMixin, TemplateView):
    template_name = "admin_console/subscriber_list.html"
    active_nav = "subscribers"
    page_title = "Subscribers"
    page_subtitle = "Monitor audience growth and delivery readiness"
    header_icon = "mail"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(get_subscriber_page_context(self.request.GET))
        return context


class WorkflowListView(AdminAccessMixin, TemplateView):
    template_name = "admin_console/workflow_list.html"
    active_nav = "workflow"
    page_title = "Workflow Monitor"
    page_subtitle = "Track pipeline run health and failures"
    header_icon = "tasks"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(get_workflow_page_context(self.request.GET))
        return context


class AdminApiView(View):
    def dispatch(self, request, *args, **kwargs):
        if not request.user.is_authenticated:
            return JsonResponse(
                error_payload(
                    code="AUTH_UNAUTHORIZED",
                    message="authentication required",
                    error_type="AuthError",
                    request=request,
                ),
                status=401,
            )
        if not request.user.is_active or not request.user.is_staff:
            return JsonResponse(
                error_payload(
                    code="AUTH_FORBIDDEN",
                    message="admin access required",
                    error_type="PermissionError",
                    request=request,
                ),
                status=403,
            )
        return super().dispatch(request, *args, **kwargs)


class DashboardApiView(AdminApiView):
    def get(self, request):
        return success_response(data=get_dashboard_data(), request=request)


class ContentListApiView(AdminApiView):
    def get(self, request):
        return success_response(data=get_content_list_data(request.GET), request=request)


class SubscriberListApiView(AdminApiView):
    def get(self, request):
        return success_response(data=get_subscriber_list_data(request.GET), request=request)


class WorkflowRunListApiView(AdminApiView):
    def get(self, request):
        return success_response(data=get_workflow_run_list_data(request.GET), request=request)


class SourceListView(AdminAccessMixin, TemplateView):
    template_name = "admin_console/source_list.html"
    active_nav = "sources"
    page_title = "Source Management"
    page_subtitle = "Manage content sources and discovery endpoints"
    header_icon = "site"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(get_source_page_context(self.request.GET))
        return context


class SourceDetailPageView(AdminAccessMixin, TemplateView):
    template_name = "admin_console/source_detail.html"
    active_nav = "sources"
    page_title = "Source Detail"
    page_subtitle = "Inspect source configuration and discovery history"
    header_icon = "site"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update({"source_detail_data": get_source_detail_data(self.kwargs["source_id"])})
        return context


class SourceListApiView(AdminApiView):
    def get(self, request):
        return success_response(data=get_source_list_data(request.GET), request=request)

    def post(self, request):
        try:
            import json
            payload = {}
            if request.body:
                try:
                    payload = json.loads(request.body)
                except json.JSONDecodeError:
                    payload = {}
            result = create_source(
                payload=payload,
                triggered_by_user=request.user,
            )
            return success_response(data=result, request=request, status=201)
        except AdminActionError as exc:
            return JsonResponse(
                error_payload(
                    code=exc.code,
                    message=exc.message,
                    error_type=exc.error_type,
                    request=request,
                    details=exc.details,
                ),
                status=exc.status,
            )


class SourceToggleApiView(AdminApiView):
    def post(self, request, source_id):
        try:
            import json
            payload = {}
            if request.body:
                try:
                    payload = json.loads(request.body)
                except json.JSONDecodeError:
                    payload = {}
            is_enabled = payload.get("is_enabled", True)
            result = update_source_configuration(
                source_id=source_id,
                payload={"is_enabled": is_enabled},
            )
            return success_response(data=result, request=request)
        except AdminActionError as exc:
            return JsonResponse(
                error_payload(
                    code=exc.code,
                    message=exc.message,
                    error_type=exc.error_type,
                    request=request,
                    details=exc.details,
                ),
                status=exc.status,
            )


class SourceDiscoveryApiView(AdminApiView):
    def post(self, request, source_id):
        try:
            result = trigger_discovery(
                payload={"source_ids": [source_id]},
                request_id=getattr(request, "request_id", None),
                triggered_by_user=request.user,
            )
            return success_response(data=result, request=request)
        except AdminActionError as exc:
            return JsonResponse(
                error_payload(
                    code=exc.code,
                    message=exc.message,
                    error_type=exc.error_type,
                    request=request,
                    details=exc.details,
                ),
                status=exc.status,
            )


class ContentDetailPageView(AdminAccessMixin, TemplateView):
    template_name = "admin_console/content_detail.html"
    active_nav = "content"
    page_title = "Content Detail"
    page_subtitle = "Inspect content item fields and processing history"
    header_icon = "doc-full-inverse"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(get_content_detail_page_context(self.kwargs["content_item_id"]))
        return context


class ContentDetailApiView(AdminApiView):
    def get(self, request, content_item_id):
        try:
            return success_response(data=get_content_detail_data(content_item_id), request=request)
        except AdminActionError as exc:
            return JsonResponse(
                error_payload(
                    code=exc.code,
                    message=exc.message,
                    error_type=exc.error_type,
                    request=request,
                ),
                status=exc.status,
            )


class ContentActionRetryStageApiView(AdminApiView):
    def post(self, request, content_item_id):
        try:
            import json
            payload = {}
            if request.body:
                try:
                    payload = json.loads(request.body)
                except json.JSONDecodeError:
                    payload = {}
            result = retry_content_stage(
                content_item_id=content_item_id,
                payload=payload,
                request_id=getattr(request, "request_id", None),
                triggered_by_user=request.user,
            )
            return success_response(data=result, request=request)
        except AdminActionError as exc:
            return JsonResponse(
                error_payload(
                    code=exc.code,
                    message=exc.message,
                    error_type=exc.error_type,
                    request=request,
                    details=exc.details,
                ),
                status=exc.status,
            )


class ContentActionPublishWebApiView(AdminApiView):
    def post(self, request, content_item_id):
        try:
            import json
            payload = {}
            if request.body:
                try:
                    payload = json.loads(request.body)
                except json.JSONDecodeError:
                    payload = {}
            result = publish_content_web(
                content_item_id=content_item_id,
                payload=payload,
                request_id=getattr(request, "request_id", None),
                triggered_by_user=request.user,
            )
            return success_response(data=result, request=request)
        except AdminActionError as exc:
            return JsonResponse(
                error_payload(
                    code=exc.code,
                    message=exc.message,
                    error_type=exc.error_type,
                    request=request,
                    details=exc.details,
                ),
                status=exc.status,
            )


class WorkflowRunDetailApiView(AdminApiView):
    def get(self, request, run_id):
        try:
            return success_response(data=get_workflow_run_timeline(run_id), request=request)
        except AdminActionError as exc:
            return JsonResponse(
                error_payload(
                    code=exc.code,
                    message=exc.message,
                    error_type=exc.error_type,
                    request=request,
                ),
                status=exc.status,
            )


class WorkflowRunRetryApiView(AdminApiView):
    def post(self, request, run_id):
        try:
            import json
            payload = {}
            if request.body:
                try:
                    payload = json.loads(request.body)
                except json.JSONDecodeError:
                    payload = {}
            stage = (payload.get("stage") or "").strip()
            if not stage:
                return JsonResponse(
                    error_payload(
                        code="VALIDATION_REQUIRED_FIELD_MISSING",
                        message="stage is required",
                        request=request,
                        details={"field": "stage"},
                    ),
                    status=400,
                )
            result = retry_workflow_run_stage(
                run_id=run_id,
                stage=stage,
                request_id=getattr(request, "request_id", None),
                triggered_by_user=request.user,
            )
            return success_response(data=result, request=request)
        except AdminActionError as exc:
            return JsonResponse(
                error_payload(
                    code=exc.code,
                    message=exc.message,
                    error_type=exc.error_type,
                    request=request,
                    details=exc.details,
                ),
                status=exc.status,
            )


class ManualIntakePageView(AdminAccessMixin, TemplateView):
    template_name = "admin_console/manual_intake.html"
    active_nav = "manual_intake"
    page_title = "Manual Intake"
    page_subtitle = "Import content by URL or enter manually"
    header_icon = "plus"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        from techbrief.apps.content_pipeline.models import Source
        context["source_choices"] = Source.objects.order_by("source_name")
        return context


class ManualIntakeApiView(AdminApiView):
    def get(self, request):
        return success_response(data={"message": "use POST to submit intake"}, request=request)

    def post(self, request):
        try:
            import json
            payload = {}
            if request.body:
                try:
                    payload = json.loads(request.body)
                except json.JSONDecodeError:
                    payload = {}
            mode = (payload.get("mode") or "").strip()
            if mode == "url":
                result = queue_manual_url_import(
                    payload=payload,
                    request_id=getattr(request, "request_id", None),
                    triggered_by_user=request.user,
                )
            elif mode == "rich_text":
                result = create_manual_content(
                    payload=payload,
                    triggered_by_user=request.user,
                )
            else:
                return JsonResponse(
                    error_payload(
                        code="VALIDATION_INVALID_BODY",
                        message="mode must be 'url' or 'rich_text'",
                        error_type="ValidationError",
                        request=request,
                        details={"field": "mode"},
                    ),
                    status=400,
                )
            return success_response(data=result, request=request)
        except AdminActionError as exc:
            return JsonResponse(
                error_payload(
                    code=exc.code,
                    message=exc.message,
                    error_type=exc.error_type,
                    request=request,
                    details=exc.details,
                ),
                status=exc.status,
            )


class ManualPublishPageView(AdminAccessMixin, TemplateView):
    template_name = "admin_console/manual_publish.html"
    active_nav = "manual_publish"
    page_title = "Manual Publish"
    page_subtitle = "Publish content to web or create WeChat drafts"
    header_icon = "upload"

    def get_context_data(self, **kwargs):
        context = super().get_context_data(**kwargs)
        context.update(get_manual_publish_page_context())
        return context


class ManualPublishApiView(AdminApiView):
    def post(self, request):
        try:
            import json
            payload = {}
            if request.body:
                try:
                    payload = json.loads(request.body)
                except json.JSONDecodeError:
                    payload = {}
            channel = (payload.get("channel") or "").strip()
            if channel == "web":
                content_item_id = payload.get("content_item_id")
                if not content_item_id:
                    return JsonResponse(
                        error_payload(
                            code="VALIDATION_REQUIRED_FIELD_MISSING",
                            message="content_item_id is required",
                            request=request,
                            details={"field": "content_item_id"},
                        ),
                        status=400,
                    )
                result = publish_content_web(
                    content_item_id=content_item_id,
                    payload=payload,
                    request_id=getattr(request, "request_id", None),
                    triggered_by_user=request.user,
                )
            elif channel == "wechat":
                result = create_wechat_draft_from_payload(
                    payload=payload,
                    request_id=getattr(request, "request_id", None),
                    triggered_by_user=request.user,
                )
            else:
                return JsonResponse(
                    error_payload(
                        code="VALIDATION_INVALID_BODY",
                        message="channel must be 'web' or 'wechat'",
                        error_type="ValidationError",
                        request=request,
                        details={"field": "channel"},
                    ),
                    status=400,
                )
            return success_response(data=result, request=request)
        except AdminActionError as exc:
            return JsonResponse(
                error_payload(
                    code=exc.code,
                    message=exc.message,
                    error_type=exc.error_type,
                    request=request,
                    details=exc.details,
                ),
                status=exc.status,
            )


class PublishWebApiView(AdminApiView):
    def post(self, request):
        try:
            import json
            payload = {}
            if request.body:
                try:
                    payload = json.loads(request.body)
                except json.JSONDecodeError:
                    payload = {}
            content_item_id = payload.get("content_item_id")
            if not content_item_id:
                return JsonResponse(
                    error_payload(
                        code="VALIDATION_REQUIRED_FIELD_MISSING",
                        message="content_item_id is required",
                        request=request,
                        details={"field": "content_item_id"},
                    ),
                    status=400,
                )
            result = publish_content_web(
                content_item_id=content_item_id,
                payload=payload,
                request_id=getattr(request, "request_id", None),
                triggered_by_user=request.user,
            )
            return success_response(data=result, request=request)
        except AdminActionError as exc:
            return JsonResponse(
                error_payload(
                    code=exc.code,
                    message=exc.message,
                    error_type=exc.error_type,
                    request=request,
                    details=exc.details,
                ),
                status=exc.status,
            )


class PublishWechatApiView(AdminApiView):
    def post(self, request):
        try:
            import json
            payload = {}
            if request.body:
                try:
                    payload = json.loads(request.body)
                except json.JSONDecodeError:
                    payload = {}

            # Handle retry action
            if payload.get("action") == "retry":
                publish_record_id = payload.get("publish_record_id")
                if not publish_record_id:
                    return JsonResponse(
                        error_payload(
                            code="VALIDATION_REQUIRED_FIELD_MISSING",
                            message="publish_record_id is required",
                            request=request,
                            details={"field": "publish_record_id"},
                        ),
                        status=400,
                    )
                result = retry_wechat_publish_record(
                    publish_record_id=publish_record_id,
                    request_id=getattr(request, "request_id", None),
                    triggered_by_user=request.user,
                )
                return success_response(data=result, request=request)

            result = create_wechat_draft_from_payload(
                payload=payload,
                request_id=getattr(request, "request_id", None),
                triggered_by_user=request.user,
            )
            return success_response(data=result, request=request)
        except AdminActionError as exc:
            return JsonResponse(
                error_payload(
                    code=exc.code,
                    message=exc.message,
                    error_type=exc.error_type,
                    request=request,
                    details=exc.details,
                ),
                status=exc.status,
            )


class SourceDetailApiView(AdminApiView):
    def get(self, request, source_id):
        try:
            return success_response(data=get_source_detail_data(source_id), request=request)
        except AdminActionError as exc:
            return JsonResponse(
                error_payload(
                    code=exc.code,
                    message=exc.message,
                    error_type=exc.error_type,
                    request=request,
                ),
                status=exc.status,
            )

    def post(self, request):
        try:
            import json
            payload = {}
            if request.body:
                try:
                    payload = json.loads(request.body)
                except json.JSONDecodeError:
                    payload = {}
            result = create_source(
                payload=payload,
                triggered_by_user=request.user,
            )
            return success_response(data=result, request=request)
        except AdminActionError as exc:
            return JsonResponse(
                error_payload(
                    code=exc.code,
                    message=exc.message,
                    error_type=exc.error_type,
                    request=request,
                    details=exc.details,
                ),
                status=exc.status,
            )


class SourceDeleteApiView(AdminApiView):
    def post(self, request, source_id):
        try:
            result = delete_source(source_id=source_id)
            return success_response(data=result, request=request)
        except AdminActionError as exc:
            return JsonResponse(
                error_payload(
                    code=exc.code,
                    message=exc.message,
                    error_type=exc.error_type,
                    request=request,
                    details=exc.details,
                ),
                status=exc.status,
            )
