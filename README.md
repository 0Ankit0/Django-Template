# django-template

This project is based on the Cookiecutter Django project template.

For local tenant routing, use domains under .localhost such as acme.localhost.

## Organizations and Invitations

The tenants app provides an owner-controlled organization membership workflow on top of `django-tenant-users`.

### Organization ownership

- A signed-in user can create an organization at `/tenants/organizations/new/`.
- The creator becomes the tenant owner and is added to the tenant with tenant-level superuser permissions.
- The tenant receives a primary domain using `<organization-slug>.<DJANGO_TENANT_USERS_DOMAIN>`.
- Only the owner can invite users from the organization at `/tenants/organization/invite/`.

### Invitation lifecycle

Invitations are stored in the shared/public schema and contain a unique, non-guessable UUID token, expiration time, status, sender, recipient, optional message, and delivery timestamps.

1. The organization owner selects an existing active user and sends an invitation.
2. The user receives an email containing an acceptance link.
3. The user must be authenticated as the invited account before the invitation can be accepted or declined.
4. Accepting the invitation calls `Tenant.add_user()` and grants tenant access only after explicit acceptance.
5. Invitations expire after seven days by default and cannot be accepted after expiry.
6. Every new invitation or resend creates a **new database row with a new token**. Any older pending invitation for the same tenant/user is canceled, so there is no invitation `send_count` or multi-send counter.

### Superuser administration

Django Admin exposes a **Tenant Invitations** model for superusers. A superuser can select any existing active user and tenant, create an invitation on their behalf, and use the **Send invitation notification** admin action to email the recipient. The recipient still has to accept the invitation; creating an invitation does not silently grant tenant access.

The invitation admin exposes status, expiry, sender, recipient, delivery timestamp, and acceptance/decline timestamps so onboarding can be audited.

After adding the invitation migrations, apply shared migrations before starting the application:

    uv run python manage.py migrate_schemas --shared
    uv run python manage.py migrate_schemas

For local email testing, configure Django's email backend in `.env` or `.envs/.local/.django`. The normal SMTP/Anymail configuration used by the project is supported.

## Billing

Billing is tenant-first and stored in the shared/public schema because a subscription belongs to a tenant, not an individual user.

The billing app provides:
