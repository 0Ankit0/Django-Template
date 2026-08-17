Billing provider sandbox credentials
=====================================

The billing template is configured for sandbox/test environments. Never use
these values for production.

Stripe
------

Stripe does not require a fixed merchant credential in the repository. Create
Stripe test-mode API keys in the Stripe Dashboard and put them in the local
environment. For Checkout card testing, Stripe documents ``4242 4242 4242
4242`` with any future expiry and any three-digit CVC as a successful test card.

Khalti
------

Khalti requires a sandbox merchant account. Khalti's official documentation
provides the following sandbox wallet credentials:

* Test Khalti ID: ``9800000000`` through ``9800000005``
* MPIN: ``1111``
* OTP: ``987654``

The server-side authorization key must come from the sandbox merchant account.
The template includes the example sandbox authorization key shown in Khalti's
official ePayment examples as a development fallback. If it is rejected, set
``KHALTI_SECRET_KEY`` to the current key from your sandbox merchant dashboard.

The sandbox API base URL is ``https://dev.khalti.com/api/v2/``.

Khalti requires the server to perform the lookup request after the callback;
the template does this before recording a successful Payment.

Reference: https://docs.khalti.com/getting-started/

Reference: https://docs.khalti.com/khalti-epayment/

eSewa
-----

eSewa provides these official UAT credentials:

* Product code: ``EPAYTEST``
* Secret key: ``8gBm/:&EnhH.1/q``
* Test eSewa ID: ``9711111111`` / ``9711111112`` / ``9711111113`` / ``9711111114``
* Password: ``Nepal@123``
* OTP/token: ``123456``

The template includes the UAT product code and secret as development defaults.
The payment response is signature-verified and then checked against eSewa's
transaction-status API before a payment is marked successful.

Reference: https://developer.esewa.com.np/pages/Test-credentials

Reference: https://developer.esewa.com.np/pages/Epay-V2

Django Admin
------------

Open ``Admin -> Billing -> Provider configurations``. The administrator can
enable or disable Stripe, Khalti, and eSewa and choose Sandbox/Test or
Live/Production mode.

Provider API secrets are intentionally **not** stored in Django Admin or in
the database. Keep them in environment variables. The admin configuration
controls availability while credentials remain outside the database.

For local development, the provider choices on the pricing page are filtered
by the admin-enabled state and by payment compatibility:

* Stripe: one-time and recurring prices.
* Khalti: one-time NPR prices.
* eSewa: one-time NPR prices.
