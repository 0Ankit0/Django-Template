from django.conf import settings


def frontend_context(request):
    """Add common context variables for all templates."""
    return {
        'app_name': 'E-Commerce',
        'debug': settings.DEBUG,
        'environment': getattr(settings, 'ENVIRONMENT_NAME', 'development'),
        'current_tenant': getattr(request, 'tenant', None),
    }
