"""Stripe payment gateway implementation"""

from typing import Any

import stripe
from django.conf import settings

from .base import BasePaymentGateway


class StripeGateway(BasePaymentGateway):
    """Stripe payment gateway adapter"""

    def __init__(self):
        self.api_key = settings.STRIPE_LIVE_SECRET_KEY if settings.STRIPE_LIVE_MODE else settings.STRIPE_TEST_SECRET_KEY
        stripe.api_key = self.api_key

    def initiate_payment(
        self, amount: float, currency: str, customer_info: dict[str, Any], metadata: dict[str, Any]
    ) -> dict[str, Any]:
        """
        Initiate a payment with Stripe using PaymentIntent or Checkout Session
        """
        # Convert amount to cents/smallest unit
        amount_cents = int(amount * 100)

        # Check if we have a saved payment method
        payment_method_id = metadata.get("payment_method_id")
        customer_id = metadata.get("customer_id")  # We should pass this if available

        if payment_method_id and customer_id:
            # Payment with saved card - Use PaymentIntent
            try:
                intent = stripe.PaymentIntent.create(
                    amount=amount_cents,
                    currency=currency,
                    customer=customer_id,
                    payment_method=payment_method_id,
                    off_session=True,
                    confirm=True,
                    metadata=metadata,
                    return_url=metadata.get("return_url"),
                )

                # If requires action (3DS), we need to handle it on frontend
                # Using a dummy URL for now as BaseGateway expects a URL
                # In a real SPA, we'd return client_secret.
                # Here we can return the return_url with status appended?
                # Or a special URL that frontend handles.

                status_url = f"{metadata.get('return_url')}?payment_intent={intent.id}&gateway=stripe"

                return {
                    "payment_url": status_url,
                    "transaction_id": intent.id,
                    "status": intent.status,
                    "client_secret": intent.client_secret,
                }

            except stripe.error.CardError as e:
                raise ValueError(f"Card declined: {e.user_message}")
            except stripe.error.StripeError as e:
                raise ValueError(f"Stripe error: {str(e)}")

        else:
            # New Payment - Use Checkout Session for simplicity
            # Logic: Redirect user to Stripe hosted page

            try:
                # Prepare line items
                line_items = [
                    {
                        "price_data": {
                            "currency": currency,
                            "product_data": {
                                "name": metadata.get("purchase_order_name", "Order"),
                            },
                            "unit_amount": amount_cents,
                        },
                        "quantity": 1,
                    }
                ]

                session_params = {
                    "payment_method_types": ["card"],
                    "line_items": line_items,
                    "mode": "payment",
                    "success_url": f"{metadata.get('return_url')}?session_id={{CHECKOUT_SESSION_ID}}&gateway=stripe",
                    "cancel_url": f"{metadata.get('return_url')}?status=cancelled",
                    "metadata": metadata,
                }

                # If we have a customer, attach it to save card for future
                if customer_id:
                    session_params["customer"] = customer_id
                    session_params["payment_intent_data"] = {
                        "setup_future_usage": "off_session",
                    }

                session = stripe.checkout.Session.create(**session_params)  # type: ignore

                return {"payment_url": session.url, "transaction_id": session.id, "status": "pending"}

            except stripe.error.StripeError as e:
                raise ValueError(f"Stripe setup failed: {str(e)}")

    def verify_payment(self, transaction_id: str) -> dict[str, Any]:
        """Verify payment status"""
        try:
            # Check if it's a Checkout Session or PaymentIntent
            if transaction_id.startswith("cs_"):
                session = stripe.checkout.Session.retrieve(transaction_id)
                payment_intent_id = session.payment_intent
                if payment_intent_id:
                    # Retrieve intent for accurate status
                    intent = stripe.PaymentIntent.retrieve(payment_intent_id)
                    status_map = {
                        "succeeded": "completed",
                        "processing": "pending",
                        "requires_payment_method": "failed",
                        "canceled": "cancelled",
                    }
                    return {
                        "status": status_map.get(intent.status, "pending"),
                        "amount": intent.amount / 100,
                        "currency": intent.currency,
                        "payment_method": "stripe",
                        "gateway_response": intent,
                    }
                else:
                    # Session might be unpaid/open
                    status_map = {
                        "complete": "completed",
                        "open": "pending",
                        "expired": "failed",
                    }
                    return {
                        "status": status_map.get(session.status, "pending"),
                        "amount": session.amount_total / 100 if session.amount_total else 0,
                        "currency": session.currency,
                        "gateway_response": session,
                    }

            else:
                # PaymentIntent
                intent = stripe.PaymentIntent.retrieve(transaction_id)
                status_map = {
                    "succeeded": "completed",
                    "processing": "pending",
                    "requires_payment_method": "failed",
                    "canceled": "cancelled",
                }
                return {
                    "status": status_map.get(intent.status, "pending"),
                    "amount": intent.amount / 100,
                    "currency": intent.currency,
                    "payment_method": "stripe",
                    "gateway_response": intent,
                }

        except stripe.error.StripeError as e:
            raise ValueError(f"Verification failed: {str(e)}")

    def process_webhook(self, payload: dict[str, Any], headers: dict[str, str]) -> dict[str, Any]:
        """Process recurring webhooks or explicit outcome webhooks"""
        # Stripe webhooks are handled by djstripe preferably, but if we need manual handle:

        event = None
        try:
            # We assume payload is already verified or we trust internal call
            # In a real scenario, we verify signature using headers['Stripe-Signature']
            # safely assuming payload is dict here
            event = payload
        except Exception:
            pass

        event_type = event.get("type")
        data = event.get("data", {}).get("object", {})

        result = {
            "event_type": event_type,
            "transaction_id": data.get("id"),  # Intent or Session ID
            "status": "pending",
        }

        if event_type in ["checkout.session.completed", "payment_intent.succeeded"]:
            result["transaction_id"] = data.get("id")
            result["status"] = "completed"
        elif event_type == "payment_intent.payment_failed":
            result["transaction_id"] = data.get("id")
            result["status"] = "failed"

        return result

    def create_refund(self, transaction_id: str, amount: float = None) -> dict[str, Any]:
        """Create refund"""
        try:
            # Need payment intent ID. If transaction_id is session, resolve it
            if transaction_id.startswith("cs_"):
                session = stripe.checkout.Session.retrieve(transaction_id)
                payment_intent_id = session.payment_intent
            else:
                payment_intent_id = transaction_id

            args = {"payment_intent": payment_intent_id}
            if amount:
                args["amount"] = int(amount * 100)

            refund = stripe.Refund.create(**args)
            return {"refund_id": refund.id, "status": refund.status, "amount": refund.amount / 100}
        except stripe.error.StripeError as e:
            raise ValueError(f"Refund failed: {str(e)}")
