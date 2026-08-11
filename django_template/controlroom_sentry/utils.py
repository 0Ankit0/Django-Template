from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any
from urllib.error import HTTPError
from urllib.parse import urlencode
from urllib.parse import urlparse
from urllib.request import Request
from urllib.request import urlopen

import sentry_sdk
from django.conf import settings

EXPECTED_INTEGRATIONS = (
    "DjangoIntegration",
    "CeleryIntegration",
    "RedisIntegration",
)


@dataclass(slots=True)
class IntegrationStatus:
    name: str
    active: bool


class SentryAPIError(Exception):
    pass


def _get_client():
    try:
        return sentry_sdk.get_client()
    except Exception:
        return None


def _get_client_options() -> dict[str, Any]:
    client = _get_client()
    return getattr(client, "options", {}) or {}


def _mask_dsn(dsn: str) -> str:
    if not dsn:
        return "Not configured"
    parsed = urlparse(dsn)
    netloc = parsed.hostname or "unknown-host"
    project = parsed.path.strip("/") or "unknown-project"
    public_key = parsed.username or "hidden"
    masked_key = public_key[:6] + "..." if len(public_key) > 6 else public_key
    return f"{parsed.scheme}://{masked_key}@{netloc}/{project}"


def _mask_token(token: str) -> str:
    if not token:
        return "Not configured"
    return f"{token[:6]}...{token[-4:]}" if len(token) > 10 else "Configured"


def get_api_settings() -> dict[str, Any]:
    base_url = getattr(settings, "SENTRY_API_BASE_URL", "https://sentry.io/api/0").rstrip("/")
    org_slug = getattr(settings, "SENTRY_ORG_SLUG", "")
    project_slug = getattr(settings, "SENTRY_PROJECT_SLUG", "")
    auth_token = getattr(settings, "SENTRY_AUTH_TOKEN", "")
    return {
        "base_url": base_url,
        "org_slug": org_slug,
        "project_slug": project_slug,
        "auth_token": auth_token,
        "default_query": getattr(settings, "SENTRY_DEFAULT_ISSUES_QUERY", "is:unresolved"),
        "enabled": bool(org_slug and auth_token),
        "masked_token": _mask_token(auth_token),
    }


def _api_request(method: str, path: str, *, params: list[tuple[str, str]] | None = None, payload: dict[str, Any] | None = None) -> Any:
    api_settings = get_api_settings()
    if not api_settings["enabled"]:
        raise SentryAPIError("Sentry API is not configured. Set SENTRY_ORG_SLUG and SENTRY_AUTH_TOKEN.")

    url = f"{api_settings['base_url']}/{path.lstrip('/')}"
    if params:
        url = f"{url}?{urlencode(params, doseq=True)}"

    data = None
    headers = {
        "Authorization": f"Bearer {api_settings['auth_token']}",
        "Accept": "application/json",
    }
    if payload is not None:
        data = json.dumps(payload).encode("utf-8")
        headers["Content-Type"] = "application/json"

    request = Request(url, data=data, headers=headers, method=method.upper())
    try:
        with urlopen(request, timeout=10) as response:
            body = response.read().decode("utf-8")
            return json.loads(body) if body else {}
    except HTTPError as exc:
        body = exc.read().decode("utf-8", errors="replace")
        try:
            error_payload = json.loads(body)
        except json.JSONDecodeError:
            error_payload = body
        raise SentryAPIError(f"Sentry API {exc.code}: {error_payload}") from exc
    except Exception as exc:
        raise SentryAPIError(f"Sentry API request failed: {exc}") from exc


def get_overview() -> dict[str, Any]:
    options = _get_client_options()
    dsn = options.get("dsn") or getattr(settings, "SENTRY_DSN", "") or ""
    transport = options.get("transport")
    integrations = get_integration_statuses()
    active_count = sum(1 for item in integrations if item.active)
    api_settings = get_api_settings()
    return {
        "sdk_initialized": bool(dsn),
        "dsn_masked": _mask_dsn(str(dsn)),
        "environment": options.get("environment") or getattr(settings, "SENTRY_ENVIRONMENT", "production"),
        "traces_sample_rate": options.get("traces_sample_rate", 0.0),
        "release": options.get("release") or "Not set",
        "server_name": options.get("server_name") or "Not set",
        "transport": getattr(transport, "__name__", None) or getattr(transport, "__class__", type(None)).__name__,
        "active_integrations": active_count,
        "expected_integrations": len(integrations),
        "api_enabled": api_settings["enabled"],
        "api_base_url": api_settings["base_url"],
        "org_slug": api_settings["org_slug"],
        "project_slug": api_settings["project_slug"] or "All accessible projects",
        "api_token": api_settings["masked_token"],
    }


def get_integration_statuses() -> list[IntegrationStatus]:
    client = _get_client()
    active = getattr(client, "integrations", {}) or {}
    active_names = set(active.keys()) if isinstance(active, dict) else {item.__class__.__name__ for item in active}
    return [IntegrationStatus(name=name, active=name in active_names) for name in EXPECTED_INTEGRATIONS]


def get_runtime_settings() -> dict[str, Any]:
    api_settings = get_api_settings()
    return {
        "dsn_configured": bool(getattr(settings, "SENTRY_DSN", "")),
        "sentry_dsn": _mask_dsn(getattr(settings, "SENTRY_DSN", "")),
        "log_level": getattr(settings, "SENTRY_LOG_LEVEL", "Not set"),
        "middleware_enabled": "sentry_sdk.integrations.django.DjangoIntegration" in str(getattr(settings, "LOGGING", {})),
        "redis_url": getattr(settings, "REDIS_URL", "Not set"),
        "celery_broker_url": getattr(settings, "CELERY_BROKER_URL", "Not set"),
        "sentry_api_base_url": api_settings["base_url"],
        "sentry_org_slug": api_settings["org_slug"] or "Not configured",
        "sentry_project_slug": api_settings["project_slug"] or "All accessible projects",
        "sentry_api_token": api_settings["masked_token"],
    }


def list_issues(*, query: str | None = None, project: str | None = None, limit: int = 25) -> list[dict[str, Any]]:
    api_settings = get_api_settings()
    params: list[tuple[str, str]] = [("limit", str(limit)), ("sort", "date")]
    params.append(("query", query if query is not None else api_settings["default_query"]))
    effective_project = project or api_settings["project_slug"]
    if effective_project:
        params.append(("project", effective_project))
    return _api_request("GET", f"organizations/{api_settings['org_slug']}/issues/", params=params)


def get_issue(issue_id: str) -> dict[str, Any]:
    api_settings = get_api_settings()
    params = [("expand", "owners")]
    return _api_request("GET", f"organizations/{api_settings['org_slug']}/issues/{issue_id}/", params=params)


def update_issue(issue_id: str, payload: dict[str, Any]) -> dict[str, Any]:
    api_settings = get_api_settings()
    return _api_request("PUT", f"organizations/{api_settings['org_slug']}/issues/{issue_id}/", payload=payload)


def build_issue_update_payload(data: dict[str, Any]) -> dict[str, Any]:
    payload: dict[str, Any] = {}
    status = (data.get("status") or "").strip()
    assigned_to = (data.get("assigned_to") or "").strip()
    priority = (data.get("priority") or "").strip()

    if status:
        payload["status"] = status
    if assigned_to:
        payload["assignedTo"] = assigned_to
    if priority:
        payload["priority"] = priority

    if data.get("toggle_subscription"):
        payload["isSubscribed"] = data.get("is_subscribed") == "true"
    if data.get("toggle_bookmark"):
        payload["isBookmarked"] = data.get("is_bookmarked") == "true"
    if data.get("toggle_seen"):
        payload["hasSeen"] = data.get("has_seen") == "true"
    if data.get("toggle_reviewed"):
        payload["inbox"] = data.get("inbox") == "true"

    return payload
