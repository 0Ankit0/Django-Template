from django.core.management.base import BaseCommand

from django_template.billing.models import Price, Product
from django_template.billing.services import create_stripe_price, create_stripe_product


class Command(BaseCommand):
    help = "Create missing Stripe products and prices for the local billing catalog."

    def handle(self, *args, **options):
        for product in Product.objects.all().order_by("pk"):
            if not product.provider_product_id:
                create_stripe_product(product)
                self.stdout.write(self.style.SUCCESS(f"Created Stripe product for {product.slug}"))
            for price in Price.objects.filter(product=product, provider_price_id__isnull=True).order_by("pk"):
                create_stripe_price(price)
                self.stdout.write(self.style.SUCCESS(f"Created Stripe price for {price}"))
