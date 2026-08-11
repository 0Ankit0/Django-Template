# django-template

Custom multi-tenant Django starter with tenant-aware auth and reusable UI components.

License: Apache Software License 2.0

## Stack

- Django 6
- PostgreSQL schema multitenancy via django-tenants
- Global user identities + tenant permissions via django-tenant-users
- Celery + Redis
- DRF + drf-spectacular
- Tailwind CSS via django-tailwind-cli + django-cotton + shadcn-django components

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

For local tenant routing, use domains under .localhost such as acme.localhost.

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

### Run tests

    uv run pytest

### Type checks

    uv run mypy django_template

### Coverage

    uv run coverage run -m pytest
    uv run coverage html

### Celery worker

    uv run celery -A config.celery_app worker -l info

### Celery beat

    uv run celery -A config.celery_app beat

## Notes

- Keep tenancy model changes in django_template/tenants.
- Keep auth profile changes in django_template/users.
- Add or customize cotton components directly in django_template/templates/cotton.
- Django admin login is overridden at django_template/templates/admin/login.html and uses the same cotton/tailwind visual system.
