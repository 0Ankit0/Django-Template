import stripe
from django import forms
from django.conf import settings
from djstripe.models import Price, Product


class PlanCreationForm(forms.Form):
    name = forms.CharField(
        label="Plan Name",
        max_length=100,
        widget=forms.TextInput(attrs={"class": "input input-bordered w-full", "placeholder": "e.g. Pro Plan"}),
    )
    description = forms.CharField(
        label="Description",
        widget=forms.Textarea(
            attrs={
                "class": "textarea textarea-bordered w-full",
                "rows": 3,
                "placeholder": "Plan features and benefits...",
            }
        ),
        required=False,
    )
    amount = forms.DecimalField(
        label="Amount",
        decimal_places=2,
        min_value=0,
        widget=forms.NumberInput(attrs={"class": "input input-bordered w-full", "placeholder": "0.00"}),
    )
    currency = forms.ChoiceField(
        label="Currency",
        choices=[("usd", "USD"), ("npr", "NPR")],
        initial="usd",
        widget=forms.Select(attrs={"class": "select select-bordered w-full"}),
    )
    interval = forms.ChoiceField(
        label="Interval",
        choices=[("month", "Monthly"), ("year", "Yearly")],
        initial="month",
        widget=forms.Select(attrs={"class": "select select-bordered w-full"}),
    )

    def save(self):
        data = self.cleaned_data

        # Check if Stripe is configured
        if "<CHANGE_ME>" in settings.STRIPE_TEST_SECRET_KEY:
            # Fallback for local testing without Stripe (Mocking)
            # Create local product/price directly
            import random
            import string

            def generate_id(prefix):
                return f"{prefix}_{''.join(random.choices(string.ascii_letters + string.digits, k=14))}"

            product = Product.objects.create(
                id=generate_id("prod"),
                name=data["name"],
                active=True,
                type="service",  # Default for plans
            )

            Price.objects.create(
                id=generate_id("price"),
                product=product,
                unit_amount_decimal=data["amount"],  # djstripe stores as decimal
                currency=data["currency"],
                active=True,
                type="recurring",
                recurring={
                    "interval": data["interval"],
                    "interval_count": 1,
                    "usage_type": "licensed",
                    "aggregate_usage": None,
                    "trial_period_days": None,
                },
            )
            return product

        else:
            # Create in Stripe
            stripe.api_key = settings.STRIPE_SECRET_KEY

            # 1. Create Product
            product_data = stripe.Product.create(
                name=data["name"],
                description=data.get("description", ""),
            )

            # 2. Create Price
            stripe.Price.create(
                product=product_data.id,
                unit_amount=int(data["amount"] * 100),  # Stripe expects cents
                currency=data["currency"],
                recurring={"interval": data["interval"]},
            )

            # Sync to local DB (djstripe usually handles webhooks, but we want immediate result)
            # We can use djstripe's sync methods
            from djstripe.models import Product as DJProduct

            return DJProduct.sync_from_stripe_data(product_data)
