from django.apps import AppConfig


class IamConfig(AppConfig):
    name = 'apps.iam'

    def ready(self):
        import apps.iam.signals  # noqa
