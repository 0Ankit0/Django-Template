import logging
from typing import Any

from django.conf import settings

logger = logging.getLogger(__name__)


class StripeService:
    """Service for interacting with Stripe API."""

    def __init__(self, tenant=None):
        import stripe

        self.stripe = stripe

        if settings.STRIPE_LIVE_MODE:
            self.stripe.api_key = settings.STRIPE_LIVE_SECRET_KEY
        else:
            self.stripe.api_key = settings.STRIPE_TEST_SECRET_KEY

        self.tenant = tenant

    # Customer Management
    def create_customer(self, email: str, name: str = None, metadata: dict = None) -> dict[str, Any]:
        """Create a new Stripe customer."""
        try:
            customer = self.stripe.Customer.create(
                email=email,
                name=name,
                metadata=metadata or {},
            )
            logger.info(f"Created Stripe customer: {customer.id}")
            return {"id": customer.id, "email": customer.email}
        except self.stripe.error.StripeError as e:
            logger.error(f"Error creating customer: {e}")
            raise

    def get_customer(self, customer_id: str) -> dict[str, Any] | None:
        """Get customer details."""
        try:
            customer = self.stripe.Customer.retrieve(customer_id)
            return {
                "id": customer.id,
                "email": customer.email,
                "name": customer.name,
                "default_payment_method": customer.invoice_settings.default_payment_method,
            }
        except self.stripe.error.StripeError as e:
            logger.error(f"Error retrieving customer: {e}")
            return None

    # Payment Methods
    def list_payment_methods(self, customer_id: str) -> list[dict[str, Any]]:
        """List payment methods for a customer."""
        try:
            payment_methods = self.stripe.PaymentMethod.list(
                customer=customer_id,
                type="card",
            )
            return [
                {
                    "id": pm.id,
                    "type": pm.type,
                    "card": {
                        "brand": pm.card.brand,
                        "last4": pm.card.last4,
                        "exp_month": pm.card.exp_month,
                        "exp_year": pm.card.exp_year,
                    }
                    if pm.card
                    else None,
                }
                for pm in payment_methods.data
            ]
        except self.stripe.error.StripeError as e:
            logger.error(f"Error listing payment methods: {e}")
            return []

    def attach_payment_method(self, payment_method_id: str, customer_id: str) -> bool:
        """Attach a payment method to a customer."""
        try:
            self.stripe.PaymentMethod.attach(
                payment_method_id,
                customer=customer_id,
            )
            return True
        except self.stripe.error.StripeError as e:
            logger.error(f"Error attaching payment method: {e}")
            return False

    def detach_payment_method(self, payment_method_id: str) -> bool:
        """Detach a payment method from a customer."""
        try:
            self.stripe.PaymentMethod.detach(payment_method_id)
            return True
        except self.stripe.error.StripeError as e:
            logger.error(f"Error detaching payment method: {e}")
            return False

    # Payment Intents
    def create_payment_intent(
        self, amount: int, currency: str = "usd", customer_id: str = None, metadata: dict = None
    ) -> dict[str, Any]:
        """Create a payment intent."""
        try:
            intent = self.stripe.PaymentIntent.create(
                amount=amount,
                currency=currency,
                customer=customer_id,
                metadata=metadata or {},
            )
            return {
                "id": intent.id,
                "client_secret": intent.client_secret,
                "status": intent.status,
            }
        except self.stripe.error.StripeError as e:
            logger.error(f"Error creating payment intent: {e}")
            raise

    def create_setup_intent(self, customer_id: str) -> dict[str, Any]:
        """Create a setup intent for saving payment methods."""
        try:
            intent = self.stripe.SetupIntent.create(
                customer=customer_id,
            )
            return {
                "id": intent.id,
                "client_secret": intent.client_secret,
            }
        except self.stripe.error.StripeError as e:
            logger.error(f"Error creating setup intent: {e}")
            raise

    # Subscriptions
    def create_subscription(self, customer_id: str, price_id: str, trial_days: int = None) -> dict[str, Any]:
        """Create a subscription for a customer."""
        try:
            params = {
                "customer": customer_id,
                "items": [{"price": price_id}],
            }
            if trial_days:
                params["trial_period_days"] = trial_days

            subscription = self.stripe.Subscription.create(**params)
            return {
                "id": subscription.id,
                "status": subscription.status,
                "current_period_start": subscription.current_period_start,
                "current_period_end": subscription.current_period_end,
            }
        except self.stripe.error.StripeError as e:
            logger.error(f"Error creating subscription: {e}")
            raise

    def get_subscription(self, subscription_id: str) -> dict[str, Any] | None:
        """Get subscription details."""
        try:
            subscription = self.stripe.Subscription.retrieve(subscription_id)
            return {
                "id": subscription.id,
                "status": subscription.status,
                "current_period_start": subscription.current_period_start,
                "current_period_end": subscription.current_period_end,
                "cancel_at_period_end": subscription.cancel_at_period_end,
                "items": [
                    {"price_id": item.price.id, "quantity": item.quantity} for item in subscription["items"].data
                ],
            }
        except self.stripe.error.StripeError as e:
            logger.error(f"Error retrieving subscription: {e}")
            return None

    def update_subscription(self, subscription_id: str, price_id: str) -> dict[str, Any]:
        """Update a subscription to a new price."""
        try:
            subscription = self.stripe.Subscription.retrieve(subscription_id)
            updated = self.stripe.Subscription.modify(
                subscription_id,
                items=[
                    {
                        "id": subscription["items"].data[0].id,
                        "price": price_id,
                    }
                ],
            )
            return {
                "id": updated.id,
                "status": updated.status,
            }
        except self.stripe.error.StripeError as e:
            logger.error(f"Error updating subscription: {e}")
            raise

    def cancel_subscription(self, subscription_id: str, at_period_end: bool = True) -> dict[str, Any]:
        """Cancel a subscription."""
        try:
            if at_period_end:
                subscription = self.stripe.Subscription.modify(
                    subscription_id,
                    cancel_at_period_end=True,
                )
            else:
                subscription = self.stripe.Subscription.delete(subscription_id)

            return {
                "id": subscription.id,
                "status": subscription.status,
                "cancel_at_period_end": getattr(subscription, "cancel_at_period_end", False),
            }
        except self.stripe.error.StripeError as e:
            logger.error(f"Error canceling subscription: {e}")
            raise

    # Invoices
    def list_invoices(self, customer_id: str, limit: int = 10) -> list[dict[str, Any]]:
        """List invoices for a customer."""
        try:
            invoices = self.stripe.Invoice.list(customer=customer_id, limit=limit)
            return [
                {
                    "id": inv.id,
                    "number": inv.number,
                    "amount_due": inv.amount_due,
                    "amount_paid": inv.amount_paid,
                    "status": inv.status,
                    "created": inv.created,
                    "invoice_pdf": inv.invoice_pdf,
                }
                for inv in invoices.data
            ]
        except self.stripe.error.StripeError as e:
            logger.error(f"Error listing invoices: {e}")
            return []

    # Products & Prices
    def list_products(self, active: bool = True) -> list[dict[str, Any]]:
        """List all products."""
        try:
            products = self.stripe.Product.list(active=active)
            return [
                {
                    "id": prod.id,
                    "name": prod.name,
                    "description": prod.description,
                    "images": prod.images,
                    "metadata": prod.metadata,
                }
                for prod in products.data
            ]
        except self.stripe.error.StripeError as e:
            logger.error(f"Error listing products: {e}")
            return []

    def list_prices(self, product_id: str = None, active: bool = True) -> list[dict[str, Any]]:
        """List prices, optionally filtered by product."""
        try:
            params = {"active": active}
            if product_id:
                params["product"] = product_id

            prices = self.stripe.Price.list(**params)
            return [
                {
                    "id": price.id,
                    "product": price.product,
                    "unit_amount": price.unit_amount,
                    "currency": price.currency,
                    "recurring": {
                        "interval": price.recurring.interval,
                        "interval_count": price.recurring.interval_count,
                    }
                    if price.recurring
                    else None,
                }
                for price in prices.data
            ]
        except self.stripe.error.StripeError as e:
            logger.error(f"Error listing prices: {e}")
            return []
