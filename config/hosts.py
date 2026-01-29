from django.conf import settings
from django_hosts import host, patterns

host_patterns = patterns(
    "",
    host(r"admin", "config.urls_admin", name="admin"),
    host(r"api", settings.ROOT_URLCONF, name="api"),
)
