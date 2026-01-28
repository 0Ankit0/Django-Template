from django.utils.deprecation import MiddlewareMixin
from sentry_sdk import capture_exception

from config import settings


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

