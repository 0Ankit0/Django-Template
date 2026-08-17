# django-template

Custom multi-tenant Django starter with tenant-aware auth, reusable UI components, and reusable Stripe billing.

License: Apache Software License 2.0

## Stack

- Django 6
- PostgreSQL schema multitenancy via django-tenants
- Global user identities + tenant permissions via django-tenant-users
- Celery + Redis
- DRF + drf-spectacular
- Django Control Room with Redis, cache, URLs, Celery, and custom Sentry panels
- Tailwind CSS via django-tailwind-cli + django-cotton + shadcn-django components
- Tenant-aware billing with Stripe Checkout, Billing Portal, subscriptions, payments, invoices, and signed webhooks

## Local Development

### 1. Install dependencies

    uv sync

If you are upgrading an older checkout that used Node Tailwind tooling, add Django Tailwind CLI explicitly:

    uv add django-tailwind-cli

Or use the reusable command:

    just setup-local

`just setup-local` runs dependency sync and `tailwind setup` so the standalone Tailwind binary is ready.

### 2. Run migrations (shared schema first)

    uv run python manage.py migrate_schemas --shared

### 3. Create public tenant

    uv run python manage.py create_public_tenant --domain_url localhost --owner_email admin@example.com

### 4. Migrate tenant schemas

    uv run python manage.py migrate_schemas

### 5. Create a tenant superuser

    uv run python manage.py create_tenant_superuser --schema public

### 6. Start the app

    uv run python manage.py runserver

Or:

    just runserver

`docker compose up` runs a one-shot local bootstrap service before Django,
Tailwind, Celery worker, and Celery Beat start. It applies shared migrations,
creates the `public` tenant for `localhost` if it does not exist, and then
migrates tenant schemas. Set `DJANGO_PUBLIC_TENANT_OWNER_EMAIL` in
`.envs/.local/.django` to choose the initial public tenant owner.

For local tenant routing, use domains under .localhost such as acme.localhost.

## Organizations and Invitations

The tenants app provides an owner-controlled organization membership workflow on top of `django-tenant-users`.

### Organization ownership

- A signed-in user can create an organization at `/tenants/organizations/new/`.
- The creator becomes the tenant owner and is added to the tenant with tenant-level superuser permissions.
- The tenant receives a primary domain using `<organization-slug>.<DJANGO_TENANT_USERS_DOMAIN>`.
- Only the owner can invite users from the organization at `/tenants/organization/invite/`.

### Invitation lifecycle

Invitations are stored in the shared/public schema and contain a unique, non-guessable UUID token, expiration time, status, sender, recipient, optional message, and notification delivery metadata.

1. The organization owner selects an existing active user and sends an invitation.
2. The user receives an email containing an acceptance link.
3. The user must be authenticated as the invited account before the invitation can be accepted or declined.
4. Accepting the invitation calls `Tenant.add_user()` and grants tenant access only after explicit acceptance.
5. Invitations expire after seven days by default and cannot be accepted after expiry.
6. Owners can resend pending invitations; the notification count and last-sent timestamp are recorded.

### Superuser administration

Django Admin exposes a **Tenant Invitations** model for superusers. A superuser can select any existing active user and tenant, create an invitation on their behalf, and use the **Send invitation notification** admin action to email the recipient. The recipient still has to accept the invitation; creating or resending an invitation does not silently grant tenant access.

The invitation admin also exposes status, expiry, sender, recipient, delivery count, and acceptance/decline timestamps so onboarding can be audited.

After adding the invitation migration, apply shared migrations before starting the application:

    uv run python manage.py migrate_schemas --shared
    uv run python python manage.py migrate_schemas

For local email testing, configure Django's email backend in `.env` or `.envs/.local/.django`. The normal SMTP/Anymail configuration used by the project is supported.

## Billing

Billing is tenant-first and stored in the shared/public schema because a subscription belongs to a tenant, not an individual user.

The billing app provides:

- `Product` and reusable `Price` records
- `Feature` and product-feature entitlements
- Stripe customer records mapped one-to-one to tenants
- Subscriptions with lifecycle state and billing periods
- Payments and invoices
- Checkout sessions
- Idempotent webhook event storage
- Stripe Checkout and Billing Portal
- A reusable `requires_feature("feature-key")` decorator
- Django admin screens for the complete catalog and billing state
- A `sync_billing_catalog` management command for creating missing Stripe Products and Prices

### Stripe configuration

Set these environment variables in local/production secrets:

    STRIPE_SECRET_KEY=sk_test_...
    STRIPE_PUBLISHABLE_KEY=pk_test_...
    STRIPE_WEBHOOK_SECRET=whsec_...

The integration intentionally uses Stripe's HTTP API directly, so the template does not add a second SDK dependency to `pyproject.toml`/`uv.lock`.

### Create products and prices

Create products, prices, and features in Django Admin, then synchronize products and prices to Stripe:

    uv run python manage.py sync_billing_catalog

The command creates missing Stripe Products and Prices and stores their provider IDs locally. Existing provider IDs are left untouched because Stripe Prices are immutable; create a new local Price when you need a new amount.

### Billing URLs

- `/billing/` — tenant billing dashboard
- `/billing/pricing/` — pricing page
- `/billing/portal/` — Stripe Billing Portal redirect
- `/billing/webhooks/stripe/` — Stripe webhook endpoint

The webhook endpoint must be configured in Stripe to point to your deployed `/billing/webhooks/stripe/` URL. Webhook signatures are verified against the raw request body and a five-minute timestamp tolerance, and events are persisted by provider event ID so Stripe retries are idempotent.

For local development, use the Stripe CLI to forward events:

    stripe listen --forward-to http://localhost:8000/billing/webhooks/stripe/

Use the webhook secret printed by the CLI as `STRIPE_WEBHOOK_SECRET`.

The application never treats the Checkout success page as proof of payment. Subscription and payment state is updated from verified Stripe webhook events.

## UI Components (django-cotton + shadcn-django)

Cotton components live in django_template/templates/cotton.

Pre-added shadcn/cotton component set includes:

- Navigation and menus: navigation_menu, dropdown_menu, multi_menu
- Layout: card, sheet, tabs, separator, accordion
- Forms: form, input, textarea, checkbox, select, combobox, label
- Feedback and overlays: alert, alert_dialog, dialog, popover, toast, progress
- Data display: table, badge, button

Custom project-level wrappers are also available:

- navbar (navbar, navbar.link)
- sidebar (sidebar, sidebar.group, sidebar.item)
- multi_menu (multi_menu, multi_menu.section, multi_menu.item)

Initialize or add more shadcn components:

    uv run shadcn_django list
    uv run shadcn_django add button
    uv run shadcn_django add card

Add and integrate the full shadcn allauth pack:

    just add-shadcn-allauth

This command runs `uvx shadcn_django@latest add allauth` and synchronizes generated templates into `django_template/templates/account` and `django_template/templates/cotton` so they are used by Django's active template path.

Build Tailwind CSS from input.css (no Node required):

    uv run python manage.py tailwind setup
    uv run python manage.py tailwind build
    uv run python manage.py tailwind watch

`tw-animate-css` is installed using the manual method recommended by shadcn-django when using django-tailwind-cli:

- `tw-animate.css` is vendored in the project root.
- `input.css` imports it with `@import "./tw-animate.css";`.

Reusable commands:

    just tailwind-setup
    just tailwind-build
    just tailwind-build-force
    just tailwind-watch

The base template already includes django_template/static/css/output.css and Alpine.js.

Component showcase page:

    /components/

The showcase includes live previews for all components, plus show-code and copy-code helpers.
It also includes instant search and category filters to quickly find components and complex compositions.

## Users

- Sign up through the allauth flow.
- Email is the login identifier.
- Tenant access is enforced by middleware.

## Operations Dashboard

This project integrates Django Control Room with the official panels that match the current stack, plus a custom Sentry panel:

- `dj_redis_panel`
- `dj_cache_panel`
- `dj_urls_panel`
- `dj_celery_panel`
- `controlroom_sentry`

The custom Sentry panel supports the main day-to-day issue operations backed by the Sentry API:

- issue list and issue detail views
- status updates
- assignment updates
- priority updates
- subscribe and unsubscribe
- bookmark and seen state updates
- review inbox state updates

Local development exposes the panels in both Django admin and the Control Room dashboard by default.
Production keeps panel registration disabled by default unless explicitly enabled with environment variables.

Default local dashboard routes:

- `/admin/dj-control-room/`
- `/admin/dj-redis-panel/`
- `/admin/dj-cache-panel/`
- `/admin/dj-urls-panel/`
- `/admin/dj-celery-panel/`
- `/admin/sentry-panel/`

If `DJANGO_ADMIN_URL` is customized, the same suffixes are mounted under that configured admin prefix.

Sentry API-backed issue management requires these environment variables:

- `SENTRY_API_BASE_URL`
- `SENTRY_ORG_SLUG`
- `SENTRY_AUTH_TOKEN`
- `SENTRY_PROJECT_SLUG` (optional default project filter)
- `SENTRY_DEFAULT_ISSUES_QUERY` (optional default issue stream query)

## Commands

### Reusable justfile commands

    just setup-local
    just check
    just migrate-shared
    just migrate-tenants
    just create-public-tenant
    just create-tenant-superuser
    just test
    just typecheck
    just tailwind-setup
    just tailwind-build
    just tailwind-build-force
    just tailwind-watch
    just add-shadcn <component>
    just add-shadcn-allauth
    uv run python manage.py sync_billing_catalog

### Run tests

    uv run pytest

### Type checks

    uv run mypy django_template

### Coverage

    uv run coverage run -m pytest
    uv run coverage html

## Notes

- Keep tenancy model changes in `django_template/tenants`.
- Keep auth profile changes in `django_template/users`.
- Billing lives in `django_template/billing` and is registered as a shared/public-schema app because its records are tenant-owned.
- Add or customize cotton components directly in `django_template/templates/cotton`.
- Django admin login is overridden at `django_template/templates/admin/login.html` and uses the same cotton/tailwind visual system.
