from django.core.management.base import BaseCommand

from django_template.billing.models import Price
from django_template.billing.models import Product
from django_template.billing.services import _stripe_request


class Command(BaseCommand):
    help = "Create missing Stripe products and prices for the local billing catalog."

    def handle(self, *args, **options):
        for product in Product.objects.all().order_by("pk"):
            if not product.provider_product_id:
                remote = _stripe_request(
                    "/products",
                    {
                        "name": product.name,
                        "description": product.description,
                        "active": product.active,
                        "metadata": {"local_product_id": str(product.pk), "slug": product.slug},
                    },
                )
                product.provider_product_id = remote["id"]
                product.save(update_fields=["provider_product_id", "updated_at"])
                self.stdout.write(self.style.SUCCESS(f"Created Stripe product {remote['id']} for {product.slug}"))

            for price in Price.objects.filter(product=product, provider_price_id="").order_by("pk"):
                payload = {
                    "product": product.provider_product_id,
                    "unit_amount": price.amount,
                    "currency": price.currency.lower(),
                    "active": price.active,
                    "metadata": {"local_price_id": str(price.pk)},
                }
                if price.is_recurring:
                    payload["recurring"] = {
                        "interval": price.interval,
                        "interval_count": price.interval_count,
                    }
                remote = _stripe_request("/prices", payload)
                price.provider_price_id = remote["id"]
                price.save(update_fields=["provider_price_id"])
                self.stdout.write(self.style.SUCCESS(f"Created Stripe price {remote['id']} for {price}"))
