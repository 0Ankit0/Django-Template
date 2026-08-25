# ruff: noqa: E501
import logging

import sentry_sdk
from sentry_sdk.integrations.celery import CeleryIntegration
from sentry_sdk.integrations.django import DjangoIntegration
from sentry_sdk.integrations.logging import LoggingIntegration
from sentry_sdk.integrations.redis import RedisIntegration

from .base import *  # noqa: F403
from .base import DATABASES
from .base import DJ_CONTROL_ROOM_SETTINGS
from .base import INSTALLED_APPS
from .base import REDIS_URL
from .base import SPECTACULAR_SETTINGS
from .base import env

SECRET_KEY = env("DJANGO_SECRET_KEY")
ALLOWED_HOSTS = env.list("DJANGO_ALLOWED_HOSTS", default=["example.com"])
DATABASES["default"]["CONN_MAX_AGE"] = env.int("CONN_MAX_AGE", default=60)
CACHES = {"default": {"BACKEND": "django_redis.cache.RedisCache", "LOCATION": REDIS_URL, "OPTIONS": {"CLIENT_CLASS": "django_redis.client.DefaultClient", "IGNORE_EXCEPTIONS": True}}}
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
SECURE_SSL_REDIRECT = env.bool("DJANGO_SECURE_SSL_REDIRECT", default=True)
SESSION_COOKIE_SECURE = True
SESSION_COOKIE_NAME = "__Secure-sessionid"
CSRF_COOKIE_SECURE = True
CSRF_COOKIE_NAME = "__Secure-csrftoken"
SECURE_HSTS_SECONDS = 60
SECURE_HSTS_INCLUDE_SUBDOMAINS = env.bool("DJANGO_SECURE_HSTS_INCLUDE_SUBDOMAINS", default=True)
SECURE_HSTS_PRELOAD = env.bool("DJANGO_SECURE_HSTS_PRELOAD", default=True)
SECURE_CONTENT_TYPE_NOSNIFF = env.bool("DJANGO_SECURE_CONTENT_TYPE_NOSNIFF", default=True)

AWS_ACCESS_KEY_ID = env("DJANGO_AWS_ACCESS_KEY_ID")
AWS_SECRET_ACCESS_KEY = env("DJANGO_AWS_SECRET_ACCESS_KEY")
AWS_SESSION_TOKEN = env("AWS_SESSION_TOKEN", default="")
AWS_STORAGE_BUCKET_NAME = env("DJANGO_AWS_STORAGE_BUCKET_NAME")
AWS_QUERYSTRING_AUTH = False
_AWS_EXPIRY = 60 * 60 * 24 * 7
AWS_S3_OBJECT_PARAMETERS = {"CacheControl": f"max-age={_AWS_EXPIRY}, s-maxage={_AWS_EXPIRY}, must-revalidate"}
AWS_S3_MAX_MEMORY_SIZE = env.int("DJANGO_AWS_S3_MAX_MEMORY_SIZE", default=100_000_000)
AWS_S3_REGION_NAME = env("DJANGO_AWS_S3_REGION_NAME", default="us-east-1")
AWS_REGION = AWS_S3_REGION_NAME
AWS_ENDPOINT_URL = env("AWS_ENDPOINT_URL", default="")
AWS_S3_CUSTOM_DOMAIN = env("DJANGO_AWS_S3_CUSTOM_DOMAIN", default=None)
aws_s3_domain = AWS_S3_CUSTOM_DOMAIN or f"{AWS_STORAGE_BUCKET_NAME}.s3.amazonaws.com"
STORAGES = {"default": {"BACKEND": "storages.backends.s3.S3Storage", "OPTIONS": {"location": "media", "file_overwrite": False, "endpoint_url": AWS_ENDPOINT_URL or None}}, "staticfiles": {"BACKEND": "whitenoise.storage.CompressedManifestStaticFilesStorage"}}
MEDIA_URL = f"https://{aws_s3_domain}/media/"

DEFAULT_FROM_EMAIL = env("DJANGO_DEFAULT_FROM_EMAIL", default="django-template <noreply@example.com>")
SERVER_EMAIL = env("DJANGO_SERVER_EMAIL", default=DEFAULT_FROM_EMAIL)
EMAIL_SUBJECT_PREFIX = env("DJANGO_EMAIL_SUBJECT_PREFIX", default="[django-template] ")
ACCOUNT_EMAIL_SUBJECT_PREFIX = EMAIL_SUBJECT_PREFIX
EMAIL_HOST = env("EMAIL_HOST")
EMAIL_PORT = env.int("EMAIL_PORT", default=587)
EMAIL_HOST_USER = env("EMAIL_HOST_USER")
EMAIL_HOST_PASSWORD = env("EMAIL_HOST_PASSWORD")
EMAIL_USE_TLS = env.bool("EMAIL_USE_TLS", default=True)
DEFAULT_FROM_EMAIL = env("DEFAULT_FROM_EMAIL")
ADMIN_URL = env("DJANGO_ADMIN_URL")

INSTALLED_APPS += ["anymail"]
EMAIL_BACKEND = "django.core.mail.backends.smtp.EmailBackend"
ANYMAIL = {}
STRIPE_SECRET_KEY = env.str("STRIPE_SECRET_KEY", default="")
STRIPE_PUBLISHABLE_KEY = env.str("STRIPE_PUBLISHABLE_KEY", default="")
STRIPE_WEBHOOK_SECRET = env.str("STRIPE_WEBHOOK_SECRET", default="")

COMPRESS_ENABLED = env.bool("COMPRESS_ENABLED", default=True)
COMPRESS_URL = STATIC_URL
COMPRESS_OFFLINE = True
COMPRESS_FILTERS = {"css": ["compressor.filters.css_default.CssAbsoluteFilter", "compressor.filters.cssmin.rCSSMinFilter"], "js": ["compressor.filters.jsmin.JSMinFilter"]}

DJ_CONTROL_ROOM_SETTINGS = {**DJ_CONTROL_ROOM_SETTINGS, "REGISTER_PANELS_IN_ADMIN": env.bool("CR_REGISTER_PANELS", default=False), "PANEL_ADMIN_REGISTRATION": {"dj_redis_panel": env.bool("CR_REGISTER_REDIS_PANEL", default=False), "dj_cache_panel": env.bool("CR_REGISTER_CACHE_PANEL", default=False), "dj_urls_panel": env.bool("CR_REGISTER_URLS_PANEL", default=False), "dj_celery_panel": env.bool("CR_REGISTER_CELERY_PANEL", default=False), "controlroom_sentry": env.bool("CR_REGISTER_SENTRY_PANEL", default=False)}}

SENTRY_DSN = env("SENTRY_DSN")
SENTRY_LOG_LEVEL = env.int("DJANGO_SENTRY_LOG_LEVEL", logging.INFO)
SENTRY_API_BASE_URL = env("SENTRY_API_BASE_URL", default="https://sentry.io/api/0")
SENTRY_ORG_SLUG = env("SENTRY_ORG_SLUG", default="")
SENTRY_PROJECT_SLUG = env("SENTRY_PROJECT_SLUG", default="")
SENTRY_AUTH_TOKEN = env("SENTRY_AUTH_TOKEN", default="")
SENTRY_DEFAULT_ISSUES_QUERY = env("SENTRY_DEFAULT_ISSUES_QUERY", default="is:unresolved")
sentry_logging = LoggingIntegration(level=SENTRY_LOG_LEVEL, event_level=logging.ERROR)
sentry_sdk.init(dsn=SENTRY_DSN, integrations=[sentry_logging, DjangoIntegration(), CeleryIntegration(), RedisIntegration()], environment=env("SENTRY_ENVIRONMENT", default="production"), traces_sample_rate=env.float("SENTRY_TRACES_SAMPLE_RATE", default=0.0))

CELERY_BEAT_SCHEDULE = {
    "retry-unprocessed-stripe-webhooks": {"task": "django_template.billing.tasks.retry_unprocessed_stripe_webhooks", "schedule": 30.0},
    "expire-billing-entitlements": {"task": "django_template.billing.tasks.expire_entitlements", "schedule": 60.0},
}

SPECTACULAR_SETTINGS["SERVERS"] = [{"url": "https://example.com", "description": "Production server"}]
