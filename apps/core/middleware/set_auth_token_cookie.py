from django.utils.deprecation import MiddlewareMixin

from iam.utils import reset_auth_cookie, set_auth_cookie
from config import settings

class SetAuthTokenCookieMiddleware:
    """Middleware for setting authentication tokens in cookies."""
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        response = self.get_response(request)

        if getattr(request, "reset_auth_cookie", False):
            reset_auth_cookie(response)

        if tokens := getattr(request, "set_auth_cookie", None):
            set_auth_cookie(response, tokens)

        return response

