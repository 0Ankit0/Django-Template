from django.apps import AppConfig


class BillingConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "django_template.billing"
    verbose_name = "Billing"

    def ready(self) -> None:
        from . import signals  # noqa: F401
