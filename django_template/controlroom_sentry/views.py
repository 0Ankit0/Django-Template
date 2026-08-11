from __future__ import annotations

from django.contrib import messages
from django.http import HttpRequest, HttpResponse
from django.shortcuts import redirect, render
import sentry_sdk

from .utils import build_issue_update_payload
from .conf import panel_config
from .utils import SentryAPIError
from .utils import get_api_settings
from .utils import get_integration_statuses
from .utils import get_issue
from .utils import list_issues
from .utils import get_overview
from .utils import get_runtime_settings
from .utils import update_issue


@panel_config.permission_required("index")
def index(request: HttpRequest) -> HttpResponse:
    context = panel_config.get_context(
        request,
        title="Sentry Panel - Overview",
        overview=get_overview(),
        runtime_settings=get_runtime_settings(),
    )
    return render(request, "admin/controlroom_sentry/index.html", context)


@panel_config.permission_required("integrations")
def integrations(request: HttpRequest) -> HttpResponse:
    context = panel_config.get_context(
        request,
        title="Sentry Panel - Integrations",
        overview=get_overview(),
        integrations=get_integration_statuses(),
    )
    return render(request, "admin/controlroom_sentry/integrations.html", context)


@panel_config.permission_required("issues")
def issues(request: HttpRequest) -> HttpResponse:
    api_settings = get_api_settings()
    issue_items: list[dict] = []
    error_message = None
    selected_query = request.GET.get("query", api_settings["default_query"])
    selected_project = request.GET.get("project", api_settings["project_slug"])

    if api_settings["enabled"]:
        try:
            issue_items = list_issues(query=selected_query, project=selected_project or None)
        except SentryAPIError as exc:
            error_message = str(exc)

    context = panel_config.get_context(
        request,
        title="Sentry Panel - Issues",
        overview=get_overview(),
        api_settings=api_settings,
        issues=issue_items,
        error_message=error_message,
        selected_query=selected_query,
        selected_project=selected_project,
    )
    return render(request, "admin/controlroom_sentry/issues.html", context)


@panel_config.permission_required("issue_detail")
def issue_detail(request: HttpRequest, issue_id: str) -> HttpResponse:
    api_settings = get_api_settings()
    error_message = None

    if request.method == "POST":
        payload = build_issue_update_payload(request.POST)
        if not payload:
            messages.warning(request, "No issue updates were submitted.")
            return redirect("controlroom_sentry:issue_detail", issue_id=issue_id)
        try:
            update_issue(issue_id, payload)
            messages.success(request, "Sentry issue updated successfully.")
        except SentryAPIError as exc:
            messages.error(request, str(exc))
        return redirect("controlroom_sentry:issue_detail", issue_id=issue_id)

    issue = None
    if api_settings["enabled"]:
        try:
            issue = get_issue(issue_id)
        except SentryAPIError as exc:
            error_message = str(exc)

    context = panel_config.get_context(
        request,
        title="Sentry Panel - Issue Detail",
        overview=get_overview(),
        api_settings=api_settings,
        issue=issue,
        issue_id=issue_id,
        error_message=error_message,
        status_choices=["unresolved", "resolved", "ignored", "resolvedInNextRelease", "muted"],
        priority_choices=["low", "medium", "high"],
    )
    return render(request, "admin/controlroom_sentry/issue_detail.html", context)


@panel_config.permission_required("test_event")
def test_event(request: HttpRequest) -> HttpResponse:
    if request.method == "POST":
        event_type = request.POST.get("event_type", "message")
        message = (request.POST.get("message") or "Control Room test event").strip()

        if not get_overview()["sdk_initialized"]:
            messages.error(request, "Sentry SDK is not configured. Set SENTRY_DSN before sending test events.")
            return redirect("controlroom_sentry:test_event")

        if event_type == "exception":
            try:
                raise RuntimeError(message)
            except RuntimeError as exc:
                event_id = sentry_sdk.capture_exception(exc)
        else:
            event_id = sentry_sdk.capture_message(message, level="error")

        sentry_sdk.flush(timeout=2.0)
        messages.success(request, f"Sent Sentry {event_type} event. Event ID: {event_id}")
        return redirect("controlroom_sentry:test_event")

    context = panel_config.get_context(
        request,
        title="Sentry Panel - Test Events",
        overview=get_overview(),
        api_settings=get_api_settings(),
    )
    return render(request, "admin/controlroom_sentry/test_event.html", context)
