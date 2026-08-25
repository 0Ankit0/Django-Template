from django.conf import settings
from django.core.management.base import BaseCommand

from django_template.billing.services import _stripe_client
from django_template.billing.stripe_webhooks import STRIPE_WEBHOOK_EVENTS


class Command(BaseCommand):
    help = "Create or update the account Stripe webhook endpoint for billing events."

    def add_arguments(self, parser):
        parser.add_argument("--url", required=True, help="Public HTTPS URL for /billing/webhooks/stripe/")
        parser.add_argument("--description", default="Django Template billing webhooks")

    def handle(self, *args, **options):
        client = _stripe_client().v1.webhook_endpoints
        url = options["url"].rstrip("/")
        payload = {
            "enabled_events": list(STRIPE_WEBHOOK_EVENTS),
            "connect": False,
            "description": options["description"],
            "metadata": {
                "project": "django-template",
                "environment": "local" if settings.DEBUG else "production",
            },
        }
        existing = next((item for item in client.list({"limit": 100}).data if item.url.rstrip("/") == url), None)
        if existing:
            endpoint = client.update(existing.id, payload)
            action = "Updated"
            secret = getattr(endpoint, "secret", None)
        else:
            endpoint = client.create({"url": url, **payload})
            action = "Created"
            secret = getattr(endpoint, "secret", None)

        self.stdout.write(self.style.SUCCESS(f"{action} Stripe webhook endpoint {endpoint.id}"))
        self.stdout.write(f"URL: {endpoint.url}")
        if secret:
            self.stdout.write("Webhook secret: " + str(secret))
            self.stdout.write(self.style.WARNING("Store the returned secret as STRIPE_WEBHOOK_SECRET and never commit it."))
        else:
            self.stdout.write(self.style.WARNING("Endpoint already existed; Stripe does not return the existing signing secret here. Keep your current STRIPE_WEBHOOK_SECRET."))
        self.stdout.write("Enabled events: " + ", ".join(STRIPE_WEBHOOK_EVENTS))
