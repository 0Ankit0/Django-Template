# ruff: noqa: ERA001, E501
"""Base settings to build other settings files upon."""
from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _

import ssl
from pathlib import Path

import environ

BASE_DIR = Path(__file__).resolve(strict=True).parent.parent.parent
# django_template/
APPS_DIR = BASE_DIR / "django_template"
env = environ.Env()

# Set default to True if using local development environment and False if using docker or production environment. You can also set the value in .env file.
READ_DOT_ENV_FILE = env.bool("DJANGO_READ_DOT_ENV_FILE", default=True)
if READ_DOT_ENV_FILE:
    # OS environment variables take precedence over variables from .env
    env.read_env(str(BASE_DIR / ".env"))

# GENERAL
# ------------------------------------------------------------------------------
DEBUG = env.bool("DJANGO_DEBUG", False)
TIME_ZONE = "UTC"
LANGUAGE_CODE = "en-us"
SITE_ID = 1
USE_I18N = True
USE_TZ = True
LOCALE_PATHS = [str(BASE_DIR / "locale")]

# DATABASES
# ------------------------------------------------------------------------------
DATABASES = {
    "default": {
        "ENGINE": "django_tenants.postgresql_backend",
        "NAME": env("POSTGRES_DB"),
        "USER": env("POSTGRES_USER"),
        "PASSWORD": env("POSTGRES_PASSWORD"),
        "HOST": env("POSTGRES_HOST"),
        "PORT": env("POSTGRES_PORT", default="5432"),
    }
}
DATABASES["default"]["ATOMIC_REQUESTS"] = True
DATABASES["default"]["ENGINE"] = "django_tenants.postgresql_backend"
DATABASE_ROUTERS = ("django_tenants.routers.TenantSyncRouter",)
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# URLS
# ------------------------------------------------------------------------------
ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"

# TENANCY
# ------------------------------------------------------------------------------
TENANT_MODEL = "tenants.Tenant"
TENANT_DOMAIN_MODEL = "tenants.Domain"
TENANT_USERS_DOMAIN = env("DJANGO_TENANT_USERS_DOMAIN", default="localhost")
PUBLIC_SCHEMA_URLCONF = "config.urls"

# APPS
# ------------------------------------------------------------------------------
DJANGO_APPS = [
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.sites",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    # "django.contrib.humanize", # Handy template tags
    "unfold",
    "django.contrib.admin",
    "django.forms",
]
THIRD_PARTY_SHARED_APPS = [
    "django_tenants",
    "tenant_users.tenants",
    "tenant_users.permissions",
    "dj_control_room_base",
    "dj_redis_panel",
    "dj_cache_panel",
    "dj_urls_panel",
    "dj_celery_panel",
    "dj_control_room",
    "dj_signals_panel",
    "django_tailwind_cli",
    "django_cotton",
    "crispy_forms",
    "imagekit",
    "crispy_bootstrap5",
    "allauth",
    "allauth.account",
    "allauth.mfa",
    "allauth.socialaccount",
    "corsheaders",
    "django_celery_beat",
    "django_celery_results",
]
THIRD_PARTY_TENANT_APPS = [
    "tenant_users.permissions",
    "django_cotton",
    "crispy_forms",
    "crispy_bootstrap5",
    "rest_framework",
    # "rest_framework.authtoken",
    "corsheaders",
    "drf_spectacular",
]
LOCAL_SHARED_APPS = [
    "django_template.tenants",
    "django_template.users",
    "django_template.controlroom_sentry",
    "django_template.billing",
]
LOCAL_TENANT_APPS: list[str] = []
SHARED_APPS = DJANGO_APPS + THIRD_PARTY_SHARED_APPS + LOCAL_SHARED_APPS
TENANT_APPS = DJANGO_APPS + THIRD_PARTY_TENANT_APPS + LOCAL_TENANT_APPS
INSTALLED_APPS = SHARED_APPS + [app for app in TENANT_APPS if app not in SHARED_APPS]

# MIGRATIONS
# ------------------------------------------------------------------------------
MIGRATION_MODULES = {"sites": "django_template.contrib.sites.migrations"}

# AUTHENTICATION
# ------------------------------------------------------------------------------
AUTHENTICATION_BACKENDS = [
    "tenant_users.permissions.backend.UserBackend",
    "allauth.account.auth_backends.AuthenticationBackend",
]
AUTH_USER_MODEL = "users.User"
LOGIN_REDIRECT_URL = "users:redirect"
LOGIN_URL = "account_login"

# PASSWORDS
# ------------------------------------------------------------------------------
PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.Argon2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2PasswordHasher",
    "django.contrib.auth.hashers.PBKDF2SHA1PasswordHasher",
    "django.contrib.auth.hashers.BCryptSHA256PasswordHasher",
]
AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# MIDDLEWARE
# ------------------------------------------------------------------------------
MIDDLEWARE = [
    "django_tenants.middleware.main.TenantMainMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "corsheaders.middleware.CorsMiddleware",
    "whitenoise.middleware.WhiteNoiseMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.locale.LocaleMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "tenant_users.tenants.middleware.TenantAccessMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    "allauth.account.middleware.AccountMiddleware",
]

# STATIC
# ------------------------------------------------------------------------------
STATIC_ROOT = str(BASE_DIR / "staticfiles")
STATIC_URL = "/static/"
STATICFILES_DIRS = [str(APPS_DIR / "static")]
STATICFILES_FINDERS = [
    "django.contrib.staticfiles.finders.FileSystemFinder",
    "django.contrib.staticfiles.finders.AppDirectoriesFinder",
]

# django-tailwind-cli
TAILWIND_CLI_SRC_CSS = env("TAILWIND_CLI_SRC_CSS", default="input.css")
TAILWIND_CLI_DIST_CSS = env("TAILWIND_CLI_DIST_CSS", default="css/output.css")
TAILWIND_CLI_AUTOMATIC_DOWNLOAD = env.bool("TAILWIND_CLI_AUTOMATIC_DOWNLOAD", default=True)

# MEDIA
# ------------------------------------------------------------------------------
MEDIA_ROOT = str(APPS_DIR / "media")
MEDIA_URL = "/media/"

# TEMPLATES
# ------------------------------------------------------------------------------
TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [str(APPS_DIR / "templates")],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.template.context_processors.i18n",
                "django.template.context_processors.media",
                "django.template.context_processors.static",
                "django.template.context_processors.tz",
                "django.contrib.messages.context_processors.messages",
                "django_template.users.context_processors.allauth_settings",
            ],
        },
    },
]

FORM_RENDERER = "django.forms.renderers.TemplatesSetting"
CRISPY_TEMPLATE_PACK = "bootstrap5"
CRISPY_ALLOWED_TEMPLATE_PACKS = "bootstrap5"
FIXTURE_DIRS = (str(APPS_DIR / "fixtures"),)

# SECURITY
# ------------------------------------------------------------------------------
SESSION_COOKIE_HTTPONLY = True
CSRF_COOKIE_HTTPONLY = True
X_FRAME_OPTIONS = "DENY"

# EMAIL
# ------------------------------------------------------------------------------
EMAIL_BACKEND = env("DJANGO_EMAIL_BACKEND", default="django.core.mail.backends.smtp.EmailBackend")
EMAIL_TIMEOUT = 5

# ADMIN
# ------------------------------------------------------------------------------
ADMIN_URL = "admin/"
ADMINS = ['"Ankit Poudyal" <ankit-poudyal@example.com>']
MANAGERS = ADMINS
DJANGO_ADMIN_FORCE_ALLAUTH = env.bool("DJANGO_ADMIN_FORCE_ALLAUTH", default=False)

# Billing providers
BILLING_STRIPE_ENABLED = env.bool("BILLING_STRIPE_ENABLED", default=True)
STRIPE_SECRET_KEY = env("STRIPE_SECRET_KEY", default="")
STRIPE_PUBLISHABLE_KEY = env("STRIPE_PUBLISHABLE_KEY", default="")
STRIPE_WEBHOOK_SECRET = env("STRIPE_WEBHOOK_SECRET", default="")
BILLING_KHALTI_ENABLED = env.bool("BILLING_KHALTI_ENABLED", default=True)
KHALTI_SECRET_KEY = env("KHALTI_SECRET_KEY", default="")
KHALTI_ENVIRONMENT = env("KHALTI_ENVIRONMENT", default="sandbox")
BILLING_ESEWA_ENABLED = env.bool("BILLING_ESEWA_ENABLED", default=True)
ESEWA_PRODUCT_CODE = env("ESEWA_PRODUCT_CODE", default="EPAYTEST")
ESEWA_SECRET_KEY = env("ESEWA_SECRET_KEY", default="")
ESEWA_ENVIRONMENT = env("ESEWA_ENVIRONMENT", default="sandbox")
AWS_S3_LOCATION = env.str("DJANGO_AWS_S3_LOCATION", default="media")
AWS_AVATAR_LAMBDA_FUNCTION_NAME = env.str("AWS_AVATAR_LAMBDA_FUNCTION_NAME", default="django-template-avatar-processor")

# LOGGING
# ------------------------------------------------------------------------------
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {"verbose": {"format": "%(levelname)s %(asctime)s %(module)s %(process)d %(thread)d %(message)s"}},
    "handlers": {"console": {"level": "DEBUG", "class": "logging.StreamHandler", "formatter": "verbose"}},
    "root": {"level": "INFO", "handlers": ["console"]},
}

REDIS_URL = env("REDIS_URL", default="redis://redis:6379/0")
REDIS_SSL = REDIS_URL.startswith("rediss://")

# Django Control Room
# ------------------------------------------------------------------------------
DJ_CONTROL_ROOM_SETTINGS = {
    "REGISTER_PANELS_IN_ADMIN": env.bool("CR_REGISTER_PANELS", default=False),
    "PANEL_ADMIN_REGISTRATION": {
        "dj_redis_panel": env.bool("CR_REGISTER_REDIS_PANEL", default=False),
        "dj_cache_panel": env.bool("CR_REGISTER_CACHE_PANEL", default=False),
        "dj_urls_panel": env.bool("CR_REGISTER_URLS_PANEL", default=False),
        "dj_celery_panel": env.bool("CR_REGISTER_CELERY_PANEL", default=False),
        "controlroom_sentry": env.bool("CR_REGISTER_SENTRY_PANEL", default=False),
    },
}

# Celery
# ------------------------------------------------------------------------------
if USE_TZ:
    CELERY_TIMEZONE = TIME_ZONE
CELERY_BROKER_URL = REDIS_URL
CELERY_BROKER_USE_SSL = {"ssl_cert_reqs": ssl.CERT_NONE} if REDIS_SSL else None
CELERY_RESULT_BACKEND = REDIS_URL
CELERY_REDIS_BACKEND_USE_SSL = CELERY_BROKER_USE_SSL
CELERY_RESULT_EXTENDED = True
CELERY_RESULT_BACKEND_ALWAYS_RETRY = True
CELERY_RESULT_BACKEND_MAX_RETRIES = 10
CELERY_ACCEPT_CONTENT = ["json"]
CELERY_TASK_SERIALIZER = "json"
CELERY_RESULT_SERIALIZER = "json"
CELERY_TASK_TIME_LIMIT = 5 * 60
CELERY_TASK_SOFT_TIME_LIMIT = 60
CELERY_BEAT_SCHEDULER = "django_celery_beat.schedulers:DatabaseScheduler"
CELERY_WORKER_SEND_TASK_EVENTS = True
CELERY_TASK_SEND_SENT_EVENT = True
CELERY_WORKER_HIJACK_ROOT_LOGGER = False

# django-allauth
# ------------------------------------------------------------------------------
ACCOUNT_ALLOW_REGISTRATION = env.bool("DJANGO_ACCOUNT_ALLOW_REGISTRATION", True)
ACCOUNT_LOGIN_METHODS = {"email"}
ACCOUNT_SIGNUP_FIELDS = ["email*", "password1*", "password2*"]
ACCOUNT_EMAIL_VERIFICATION = "mandatory"
ACCOUNT_ADAPTER = "django_template.users.adapters.AccountAdapter"
ACCOUNT_FORMS = {"signup": "django_template.users.forms.UserSignupForm"}
SOCIALACCOUNT_ADAPTER = "django_template.users.adapters.SocialAccountAdapter"
SOCIALACCOUNT_FORMS = {"signup": "django_template.users.forms.UserSocialSignupForm"}

# django-compressor
# ------------------------------------------------------------------------------
INSTALLED_APPS += ["compressor"]
STATICFILES_FINDERS += ["compressor.finders.CompressorFinder"]

# django-rest-framework
# ------------------------------------------------------------------------------
REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": (
        "rest_framework.authentication.SessionAuthentication",
        "rest_framework.authentication.TokenAuthentication",
    ),
    "DEFAULT_PERMISSION_CLASSES": ("rest_framework.permissions.IsAuthenticated",),
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}
CORS_URLS_REGEX = r"^/api/.*$"
SPECTACULAR_SETTINGS = {
    "TITLE": "django-template API",
    "DESCRIPTION": "Documentation of API endpoints of django-template",
    "VERSION": "1.0.0",
    "SERVE_PERMISSIONS": ["rest_framework.permissions.IsAdminUser"],
    "SCHEMA_PATH_PREFIX": "/api/",
}

UNFOLD = {
    "SIDEBAR": {"show_search": True, "show_all_applications": True},
    "SITE_DROPDOWN": [
        {"icon": "diamond", "title": _("My site"), "link": "https://example.com", "attrs": {"target": "_blank"}},
        {"icon": "diamond", "title": _("My site"), "link": reverse_lazy("admin:index")},
    ],
}
