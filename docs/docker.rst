Docker and Compose
======================================================================

Overview
----------------------------------------------------------------------

This project provides three Compose entry points:

- ``docker-compose.local.yml`` for local development
- ``docker-compose.production.yml`` for production-like deployment
- ``docker-compose.docs.yml`` for Sphinx documentation

Local Stack
----------------------------------------------------------------------

Start local services::

    docker compose -f docker-compose.local.yml up --build

If your Docker installation uses the legacy CLI, use::

    docker-compose -f docker-compose.local.yml up --build

Main local services:

- ``django``: Runs migrations, builds Tailwind CSS, serves ASGI app with reload.
- ``tailwind``: Runs ``python manage.py tailwind watch`` to keep CSS updated.
- ``postgres``: Local PostgreSQL database.
- ``redis``: Broker/cache for celery and app usage.
- ``mailpit``: Local email inbox UI on port 8025.
- ``celeryworker`` and ``celerybeat``: Background workers and scheduling.
- Sentry monitoring is surfaced through the custom Django Control Room Sentry panel instead of Flower.

Production Stack
----------------------------------------------------------------------

Start production services::

    docker compose -f docker-compose.production.yml up --build -d

Legacy CLI alternative::

    docker-compose -f docker-compose.production.yml up --build -d

Production django startup flow:

1. Optional tenant migrations when ``DJANGO_RUN_MIGRATIONS=True``.
2. ``python /app/manage.py tailwind build``
3. ``python /app/manage.py collectstatic --noinput``
4. Optional ``python /app/manage.py compress`` when ``COMPRESS_ENABLED=true``
5. Start gunicorn with uvicorn worker.

This ensures static CSS is generated and collected before serving traffic.

Docs Stack
----------------------------------------------------------------------

Start docs service::

    docker compose -f docker-compose.docs.yml up --build

Legacy CLI alternative::

    docker-compose -f docker-compose.docs.yml up --build

The docs container runs ``make livehtml`` and serves docs on port 9000.

Operational Notes
----------------------------------------------------------------------

- Local Django and Tailwind containers share the same project volume, so template/style updates are reflected in watch mode.
- Tailwind CLI binary is managed by ``django-tailwind-cli`` and stored under ``.django_tailwind_cli``.
- If CSS appears stale, force rebuild with::

      uv run python manage.py tailwind build --force

Environment Variables
----------------------------------------------------------------------

Important variables for container behavior:

- ``DJANGO_SETTINGS_MODULE``
    - Local: ``config.settings.local``
    - Production: ``config.settings.production``
- ``DJANGO_RUN_MIGRATIONS``
    - Local default: ``True``
    - Production default: ``False`` (set to ``True`` during controlled deploys)
- ``TAILWIND_CLI_AUTOMATIC_DOWNLOAD``
    - Local default: ``True``
    - Production default: ``False`` (binary is prepared during image build)
- ``DJANGO_TENANT_USERS_DOMAIN``
    - Local: ``localhost``
    - Production: your primary domain (for tenant-aware auth/user behavior)
- ``CR_REGISTER_PANELS``
    - Local default: ``True``
    - Production default: ``False``
- ``CR_REGISTER_REDIS_PANEL``, ``CR_REGISTER_CACHE_PANEL``, ``CR_REGISTER_URLS_PANEL``, ``CR_REGISTER_CELERY_PANEL``
    - Per-panel overrides for whether each Control Room panel should also appear directly in Django admin.
- ``CR_REGISTER_SENTRY_PANEL``
    - Controls whether the custom Sentry panel is also registered directly in Django admin.
- ``SENTRY_API_BASE_URL``
    - Defaults to ``https://sentry.io/api/0``.
- ``SENTRY_ORG_SLUG`` and ``SENTRY_AUTH_TOKEN``
    - Required for the custom Sentry panel's issue-management pages.
- ``SENTRY_PROJECT_SLUG``
    - Optional default project filter for the issue stream.
- ``SENTRY_DEFAULT_ISSUES_QUERY``
    - Optional default Sentry issue search query, defaulting to ``is:unresolved``.
