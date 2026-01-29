from django.db import DEFAULT_DB_ALIAS, connections
from django.db.migrations.executor import MigrationExecutor
from django.http import HttpResponse
from django.utils.deprecation import MiddlewareMixin
from rest_framework import status
from sentry_sdk import capture_exception

from iam.utils import reset_auth_cookie, set_auth_cookie
from config import settings


class HealthCheckMiddleware(MiddlewareMixin):
    def process_request(self, request):
        if request.META["PATH_INFO"] == "/lbcheck":
            response = HttpResponse()

            executor = MigrationExecutor(connections[DEFAULT_DB_ALIAS])
            plan = executor.migration_plan(executor.loader.graph.leaf_nodes())
            if plan:
                response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE

            return response


class SetAuthTokenCookieMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        if getattr(request, "reset_auth_cookie", False):
            reset_auth_cookie(response)

        if tokens := getattr(request, "set_auth_cookie", None):
            set_auth_cookie(response, tokens)

        return response


class SentryMiddleware:
    """Middleware for capturing exceptions to Sentry"""

    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        try:
            response = self.get_response(request)
            return response
        except Exception as e:
            capture_exception(e)
            raise

    @staticmethod
    def _get_validation_error_first_detail(detail):
        if isinstance(detail, (list, dict)):
            return next(iter(detail), detail)
        return detail


class ManageCookiesMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        if (cookies := getattr(request, "set_cookies", None)) and response.status_code == 200:  # noqa: PLR2004
            for key, value in cookies.items():
                response.set_cookie(key, value, max_age=settings.COOKIE_MAX_AGE, httponly=True)

        if delete_cookies := getattr(request, "delete_cookies", []):
            for cookie in delete_cookies:
                response.delete_cookie(cookie)

        return response
