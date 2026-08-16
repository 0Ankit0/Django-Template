Billing providers
=================

The billing app is tenant-first and supports Stripe, Khalti, and eSewa. The pricing page lets a customer choose the provider for each eligible price.

Provider capabilities
---------------------

* Stripe: one-time payments and recurring subscriptions.
* Khalti: one-time NPR payments through Khalti ePayment v2.
* eSewa: one-time NPR payments through ePay v2.

Khalti and eSewa are intentionally not presented for recurring prices. They are modeled as wallet payments in this template; Stripe remains the automatic recurring-subscription provider.

Environment
-----------

Set these values in the Django environment:

``BILLING_STRIPE_ENABLED``
    Enable or disable Stripe.
``STRIPE_SECRET_KEY`` / ``STRIPE_PUBLISHABLE_KEY`` / ``STRIPE_WEBHOOK_SECRET``
    Stripe credentials and webhook signing secret.
``BILLING_KHALTI_ENABLED`` / ``KHALTI_SECRET_KEY`` / ``KHALTI_ENVIRONMENT``
    Khalti configuration. Use ``sandbox`` while testing.
``BILLING_ESEWA_ENABLED`` / ``ESEWA_PRODUCT_CODE`` / ``ESEWA_SECRET_KEY`` / ``ESEWA_ENVIRONMENT``
    eSewa configuration. Use ``sandbox`` while testing.

Checkout
--------

Create products, prices, and features in Django Admin. Recurring Stripe prices must be synchronized with:

``uv run python manage.py sync_billing_catalog``

The checkout endpoint receives the selected provider as ``provider``. The server validates that the provider is enabled and compatible with the price before starting checkout.

Webhooks and callbacks
----------------------

Stripe webhooks are received at ``/billing/webhooks/stripe/`` and require a valid ``Stripe-Signature`` header. Khalti returns to ``/billing/callback/khalti/`` and the server performs a server-to-server lookup before recording a successful payment. eSewa returns an encoded response to ``/billing/callback/esewa/``; the signature is verified and the transaction status is checked server-to-server before recording success.

Security
--------

Never trust a browser redirect alone as proof of payment. Never store card details in Django. Keep provider secrets in environment variables and use HTTPS for production callback/webhook URLs.
