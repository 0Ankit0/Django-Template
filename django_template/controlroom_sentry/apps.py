from django.apps import AppConfig


class ControlRoomSentryConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "django_template.controlroom_sentry"
    label = "controlroom_sentry"
    verbose_name = "Sentry Panel"

    def ready(self):
        from dj_control_room.registry import registry

        from .panel import SentryPanel

        registry.register(SentryPanel, panel_id="controlroom_sentry")
