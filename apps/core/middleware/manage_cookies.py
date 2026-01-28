from django.http import HttpResponse
from django.utils.deprecation import MiddlewareMixin
from config import settings

class ManageCookiesMiddleware(MiddlewareMixin):
    """Middleware for managing cookies."""
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
