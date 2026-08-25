Billing providers
=================

The billing app is tenant-first and supports Stripe, Khalti, and eSewa. Prices use
the existing ``Price.interval`` and ``Price.interval_count`` fields as the
canonical billing duration. There is no separate billing-mode column.

Provider capabilities
---------------------

* Stripe: recurring subscriptions and one-time purchases.
* Khalti: one-time NPR payments through Khalti ePayment v2.
* eSewa: one-time NPR payments through ePay v2.

One-time purchase semantics
----------------------------

A one-time price is represented using the existing ``Price.metadata`` field
(``{"one_time": true}``) plus its normal duration interval. For one-time prices,
``interval_count`` is always ``1``. The interval itself is the lifetime: for
example, a monthly one-time price remains active for one month and a weekly
one-time price remains active for one week.

After successful payment, all providers create a local ``Subscription`` record
for the purchase. It has ``current_period_start``, ``current_period_end`` and
``cancel_at_period_end=True``. A one-time purchase is therefore represented by
the same subscription model as a recurring purchase, but it can never renew.
A periodic Celery task marks it canceled once ``current_period_end`` is reached.

Stripe one-time Checkout sessions use Stripe payment mode and enable Stripe
invoice creation, so the successful payment still produces a Stripe invoice.
The resulting payment, invoice and local subscription are populated from
Stripe webhook events rather than from the browser success redirect.

Provider selection
------------------

The checkout endpoint receives the selected provider as ``provider``. The
server validates that the provider is enabled and compatible with the price.
Khalti and eSewa are exposed only for prices marked one-time because those
providers are configured as one-time wallets in this template.

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

Provider secrets are never stored in Django Admin. Admin stores only whether a
provider is enabled and whether the configured provider mode is Sandbox/Test
or Live/Production.

Checkout
--------

Create products, prices, and features in Django Admin. Synchronize the billing
catalog with::

    uv run python manage.py sync_billing_catalog

Configure the Stripe account webhook endpoint with::

    uv run python manage.py configure_stripe_webhook \
      --url https://example.com/billing/webhooks/stripe/

The command is idempotent by endpoint URL and enables only the Stripe events
used by this application: Checkout Session completion/expiration/async payment
outcomes, PaymentIntent lifecycle events, customer subscription lifecycle and
pending-update events, invoice lifecycle/payment events, and refund/charge
refund events. It creates an account endpoint (``connect=False``); this project
does not use Stripe Connect.

The endpoint's returned signing secret belongs in ``STRIPE_WEBHOOK_SECRET``.
The server stores each incoming Stripe event in ``WebhookEvent`` using the
Stripe event ID as the idempotency key before queueing background processing.

For local development, run the billing tests with::

    uv run pytest django_template/billing/tests.py django_template/billing/tests/test_services.py

Or run the complete project test suite with::

    uv run pytest

Webhooks and callbacks
----------------------

Stripe webhooks are received at ``/billing/webhooks/stripe/`` and require a
valid ``Stripe-Signature`` header. Webhook rows are unique per provider/event
ID and are processed asynchronously through Celery with retry support.

Khalti returns to ``/billing/callback/khalti/`` and the server performs a
server-to-server lookup before recording success. eSewa returns an encoded
response to ``/billing/callback/esewa/``; the signature is verified and the
transaction status is checked server-to-server before recording success. Both
callback results are stored in ``WebhookEvent`` using provider-specific event
IDs, so replayed callbacks do not create duplicate payment or subscription
records.

Success and cancellation pages
------------------------------

Stripe Checkout returns to ``/billing/success/`` or ``/billing/cancelled/``.
Khalti and eSewa verified callbacks redirect to the same success page family,
while failed/canceled provider flows redirect to the cancellation page. These
pages are built from the project's Cotton components and explicitly explain
that access is granted only after verified provider processing.

Security
--------

Never trust a browser redirect alone as proof of payment. Never store card
details in Django. Keep provider secrets in environment variables and use HTTPS
for production callback/webhook URLs. Do not commit real API keys, webhook
secrets, or merchant credentials to the repository.
