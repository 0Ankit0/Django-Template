from rest_framework.views import exception_handler
from rest_framework.response import Response


def custom_exception_handler(exc, context):
    """
    Custom exception handler for Django REST Framework.
    Provides consistent error response format.
    """
    response = exception_handler(exc, context)

    if response is not None:
        # Customize the response data
        custom_response_data = {
            'error': True,
            'status_code': response.status_code,
            'message': str(exc),
            'details': response.data if hasattr(response, 'data') else None
        }
        response.data = custom_response_data

    return response

def get_client_ip(request):
    """Retrieve client ip from x-forwarded-for header in case of load balancer usage"""
    if x_forwarded_for := request.META.get("x-forwarded-for"):
        return x_forwarded_for.split(",")[0]

    return request.META["REMOTE_ADDR"]