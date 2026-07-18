from django.apps import AppConfig


class TenancyConfig(AppConfig):
    name = 'apps.tenancy'

    def ready(self):
        import apps.users.signals  # noqa