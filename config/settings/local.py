from urllib.parse import urlparse

from .base import *  # noqa: F403
from .base import DJ_CONTROL_ROOM_SETTINGS
from .base import INSTALLED_APPS
from .base import MIDDLEWARE
from .base import env

DEBUG = True
SECRET_KEY = env("DJANGO_SECRET_KEY")
ALLOWED_HOSTS = ["localhost", ".localhost", "0.0.0.0", "127.0.0.1", "django", ".django"]  # noqa: S104

CACHES = {"default": {"BACKEND": "django.core.cache.backends.locmem.LocMemCache", "LOCATION": ""}}
EMAIL_BACKEND = env.str("DJANGO_EMAIL_BACKEND", default="django.core.mail.backends.console.EmailBackend")
EMAIL_HOST = env("EMAIL_HOST")
EMAIL_PORT = 1025
INSTALLED_APPS = ["whitenoise.runserver_nostatic", *INSTALLED_APPS]
INSTALLED_APPS += ["debug_toolbar"]
MIDDLEWARE += ["debug_toolbar.middleware.DebugToolbarMiddleware"]
DEBUG_TOOLBAR_CONFIG = {
    "DISABLE_PANELS": ["debug_toolbar.panels.redirects.RedirectsPanel", "debug_toolbar.panels.profiling.ProfilingPanel"],
    "SHOW_TEMPLATE_CONTEXT": True,
}
INTERNAL_IPS = ["127.0.0.1", "10.0.2.2"]
if env("USE_DOCKER") == "yes":
    import socket
    hostname, _, ips = socket.gethostbyname_ex(socket.gethostname())
    INTERNAL_IPS += [".".join([*ip.split(".")[:-1], "1"]) for ip in ips]
INSTALLED_APPS += ["django_extensions"]

INSTALLED_APPS += []
STRIPE_API_KEY = env.str("STRIPE_API_KEY", default="")
STRIPE_PUBLISHABLE_KEY = env.str("STRIPE_PUBLISHABLE_KEY", default="")
STRIPE_WEBHOOK_SECRET = env.str("STRIPE_WEBHOOK_SECRET", default="")

DJ_CONTROL_ROOM_SETTINGS = {
    **DJ_CONTROL_ROOM_SETTINGS,
    "REGISTER_PANELS_IN_ADMIN": env.bool("CR_REGISTER_PANELS", default=True),
    "PANEL_ADMIN_REGISTRATION": {
        "dj_redis_panel": env.bool("CR_REGISTER_REDIS_PANEL", default=True),
        "dj_cache_panel": env.bool("CR_REGISTER_CACHE_PANEL", default=True),
        "dj_urls_panel": env.bool("CR_REGISTER_URLS_PANEL", default=True),
        "dj_signals_panel": env.bool("CR_REGISTER_SIGNALS_PANEL", default=True),
        "dj_celery_panel": env.bool("CR_REGISTER_CELERY_PANEL", default=True),
        "controlroom_sentry": env.bool("CR_REGISTER_SENTRY_PANEL", default=True),
    },
}
REDIS_URL = env.str("REDIS_URL", default="redis://redis:6379/0")
redis_url = urlparse(url=REDIS_URL)
DJ_REDIS_PANEL_SETTINGS = {
    "ALLOW_KEY_DELETE": False,
    "ALLOW_KEY_EDIT": False,
    "ALLOW_TTL_UPDATE": False,
    "CURSOR_PAGINATED_SCAN": False,
    "CURSOR_PAGINATED_COLLECTIONS": False,
    "socket_timeout": 5.0,
    "socket_connect_timeout": 5.0,
    "INSTANCES": {
        "local_redis": {
            "description": "Local Redis Instance",
            "host": redis_url.hostname or "redis",
            "port": redis_url.port or 6379,
            "features": {
                "ALLOW_KEY_DELETE": True,
                "ALLOW_KEY_EDIT": True,
                "ALLOW_TTL_UPDATE": True,
                "CURSOR_PAGINATED_SCAN": True,
                "CURSOR_PAGINATED_COLLECTIONS": True,
            },
        },
    },
}
CELERY_TASK_EAGER_PROPAGATES = True

AWS_ACCESS_KEY_ID = env.str("DJANGO_AWS_ACCESS_KEY_ID", default="test")
AWS_SECRET_ACCESS_KEY = env.str("DJANGO_AWS_SECRET_ACCESS_KEY", default="test")
AWS_SESSION_TOKEN = env.str("AWS_SESSION_TOKEN", default="")
AWS_REGION = env.str("DJANGO_AWS_S3_REGION_NAME", default="us-east-1")
AWS_ENDPOINT_URL = env.str("AWS_ENDPOINT_URL", default="http://floci:4566")
AWS_STORAGE_BUCKET_NAME = env.str("DJANGO_AWS_STORAGE_BUCKET_NAME", default="django-template-media")
AWS_S3_REGION_NAME = AWS_REGION
AWS_QUERYSTRING_AUTH = False
AWS_S3_MAX_MEMORY_SIZE = env.int("DJANGO_AWS_S3_MAX_MEMORY_SIZE", default=100_000_000)
AWS_S3_CUSTOM_DOMAIN = env.str("DJANGO_AWS_S3_CUSTOM_DOMAIN", default="")
AWS_S3_ADDRESSING_STYLE = "path"
AWS_S3_OBJECT_PARAMETERS = {"CacheControl": "max-age=604800, s-maxage=604800, must-revalidate"}
AWS_S3_LOCATION = env.str("DJANGO_AWS_S3_LOCATION", default="media")
AWS_AVATAR_LAMBDA_FUNCTION_NAME = env.str("AWS_AVATAR_LAMBDA_FUNCTION_NAME", default="django-template-avatar-processor")

STORAGES = {
    "default": {
        "BACKEND": "storages.backends.s3.S3Storage",
        "OPTIONS": {
            "location": AWS_S3_LOCATION,
            "file_overwrite": False,
            "endpoint_url": AWS_ENDPOINT_URL,
            "bucket_name": AWS_STORAGE_BUCKET_NAME,
            "region_name": AWS_REGION,
            "addressing_style": AWS_S3_ADDRESSING_STYLE,
        },
    },
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}

CELERY_BEAT_SCHEDULE = {
    "retry-unprocessed-stripe-webhooks": {"task": "django_template.billing.tasks.retry_unprocessed_stripe_webhooks", "schedule": 30.0},
    "expire-one-time-purchases": {"task": "django_template.billing.tasks.expire_one_time_purchases", "schedule": 60.0},
}
