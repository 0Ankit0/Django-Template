"""
With these settings, tests run faster.
"""

from .base import *  # noqa: F403
from .base import TEMPLATES
from .base import env

SECRET_KEY = env(
    "DJANGO_SECRET_KEY",
    default="dOkwNN6gnPOGZpP2srOLxPi2xJUsAeTtE0enoopoW3oWKDcZJMeG51lQ170giY2L",
)
TEST_RUNNER = "django.test.runner.DiscoverRunner"
PASSWORD_HASHERS = ["django.contrib.auth.hashers.MD5PasswordHasher"]
EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"
TEMPLATES[0]["OPTIONS"]["debug"] = True  # type: ignore[index]
MEDIA_URL = "http://media.testserver/"

INSTALLED_APPS += ["django_template.billing"]
STRIPE_SECRET_KEY = env.str("STRIPE_SECRET_KEY", default="sk_test_placeholder")
STRIPE_PUBLISHABLE_KEY = env.str("STRIPE_PUBLISHABLE_KEY", default="pk_test_placeholder")
STRIPE_WEBHOOK_SECRET = env.str("STRIPE_WEBHOOK_SECRET", default="whsec_test_placeholder")
