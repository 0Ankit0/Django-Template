from django.conf import settings
from django.core.management.base import BaseCommand

from django_template.billing.services import _stripe_client
from django_template.billing.stripe_webhooks import STRIPE_WEBHOOK_EVENTS


class Command(BaseCommand):
    help = "Create the account Stripe webhook endpoint for billing events."

    def add_arguments(self, parser):
        parser.add_argument("--url", required=True, help="Public HTTPS URL for /billing/webhooks/stripe/")
        parser.add_argument("--description", default="Django Template billing webhooks")

    def handle(self, *args, **options):
        endpoint = _stripe_client().v1.webhook_endpoints.create(
            {
                "url": options["url"].rstrip("/"),
                "enabled_events": list(STRIPE_WEBHOOK_EVENTS),
                "connect": False,
                "description": options["description"],
                "metadata": {
                    "project": "django-template",
                    "environment": "local" if settings.DEBUG else "production",
                },
            },
        )
        self.stdout.write(self.style.SUCCESS(f"Created Stripe webhook endpoint {endpoint.id}"))
        self.stdout.write(f"URL: {endpoint.url}")
        self.stdout.write("Webhook secret: " + str(endpoint.secret))
        self.stdout.write("Enabled events: " + ", ".join(STRIPE_WEBHOOK_EVENTS))
        self.stdout.write(self.style.WARNING("Store the returned secret as STRIPE_WEBHOOK_SECRET and never commit it."))
