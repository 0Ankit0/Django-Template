"""
ASGI routing configuration for WebSocket connections.
Works alongside REST API for real-time features.
"""
from channels.auth import AuthMiddlewareStack
from channels.routing import ProtocolTypeRouter, URLRouter
from channels.security.websocket import AllowedHostsOriginValidator
from django.core.asgi import get_asgi_application
from django.urls import re_path

from apps.websockets.consumers import NotificationConsumer, TenantConsumer

# Get the Django ASGI application
django_asgi_app = get_asgi_application()

websocket_urlpatterns = [
    re_path(r'ws/notifications/$', NotificationConsumer.as_asgi()),  # type: ignore
    re_path(r'ws/tenant/(?P<tenant_id>\w+)/$', TenantConsumer.as_asgi()),  # type: ignore
]

application = ProtocolTypeRouter({
    'http': django_asgi_app,
    'websocket': AllowedHostsOriginValidator(
        AuthMiddlewareStack(
            URLRouter(websocket_urlpatterns)
        )
    ),
})
