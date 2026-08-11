from dj_control_room_base.core import PanelPlugin


class SentryPanel(PanelPlugin):
    name = "Sentry Panel"
    description = "Inspect Sentry SDK configuration, integrations, and send test events"
    icon = "shield"
    icon_color = "danger"
    features = [
        "Review Sentry DSN, environment, transport, and sample rates",
        "Inspect active Django, Celery, and Redis Sentry integrations",
        "Send test message and exception events directly from the admin",
        "Verify runtime initialization without leaving Django admin",
    ]

    app_name = "controlroom_sentry"
    docs_url = "https://docs.sentry.io/platforms/python/guides/django/"

    def get_url_name(self):
        return "index"

    def get_config(self):
        from .conf import panel_config

        return panel_config
