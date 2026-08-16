Billing providers
=================

The billing app is tenant-first and supports Stripe, Khalti, and eSewa. The
pricing page lets a customer choose the provider for each eligible price.

Provider capabilities
---------------------

* Stripe: one-time payments and recurring subscriptions.
* Khalti: one-time NPR payments through Khalti ePayment v2.
* eSewa: one-time NPR payments through ePay v2.

Khalti and eSewa are intentionally not presented for recurring prices. They
are modeled as wallet payments in this template; Stripe remains the automatic
recurring-subscription provider.

Provider selection
------------------

The customer submits a provider choice with checkout. The server validates
both the provider and the price before creating a payment. A provider must be
enabled in ``Admin -> Billing -> Provider configurations`` and must support the
selected price. Recurring prices are restricted to Stripe.

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

Create products, prices, and features in Django Admin. Recurring Stripe prices
must be synchronized with::

    uv run python manage.py sync_billing_catalog

The checkout endpoint receives the selected provider as ``provider``. The
server validates that the provider is enabled and compatible with the price
before starting checkout.

For local development, run the billing tests with::

    uv run pytest django_template/billing/tests.py

Or run the complete project test suite with::

    uv run pytest

The billing test suite covers:

* smallest-currency-unit price handling
* product/feature relationships and uniqueness
* provider configuration records
* Stripe webhook signature verification and replay tolerance
* eSewa response signature verification and tamper rejection
* Khalti checkout creation and recurring-price rejection
* eSewa signed checkout form generation
* Billing model registration in Django Admin

Sandbox test credentials
------------------------

See ``billing-test-credentials.rst`` for the documented Stripe, Khalti, and
eSewa sandbox/UAT test credentials. Those credentials are for development only
and must never be used in production configuration.

Webhooks and callbacks
----------------------

Stripe webhooks are received at ``/billing/webhooks/stripe/`` and require a
valid ``Stripe-Signature`` header. Khalti returns to
``/billing/callback/khalti/`` and the server performs a server-to-server lookup
before recording a successful payment. eSewa returns an encoded response to
``/billing/callback/esewa/``; the signature is verified and the transaction
status is checked server-to-server before recording success.

Security
--------

Never trust a browser redirect alone as proof of payment. Never store card
details in Django. Keep provider secrets in environment variables and use HTTPS
for production callback/webhook URLs. Do not commit real API keys, webhook
secrets, or merchant credentials to the repository.
