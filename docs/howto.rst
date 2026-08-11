How To
======================================================================

Local Development Workflow
----------------------------------------------------------------------

Use the reusable commands from ``justfile`` for day-to-day work::

    just setup-local
    just check
    just runserver

Tenant setup helpers::

    just migrate-shared
    just create-public-tenant
    just migrate-tenants
    just create-tenant-superuser

Tailwind CSS (Node-free)
----------------------------------------------------------------------

This project uses ``django-tailwind-cli`` and does not require Node.js.

To match shadcn-django guidance for non-Node setups, ``tw-animate-css`` is integrated via the manual download method.

Manual setup reference:

- ``tw-animate.css`` is stored at project root.
- ``input.css`` includes ``@import "./tw-animate.css";``.

Initialize CLI binary and build output CSS::

    just tailwind-setup
    just tailwind-build

For active development, run Tailwind watcher::

    just tailwind-watch

Input and output paths are configured in Django settings:

- ``TAILWIND_CLI_SRC_CSS = input.css``
- ``TAILWIND_CLI_DIST_CSS = css/output.css``

Templates and Components
----------------------------------------------------------------------

Add shadcn-django components::

    just add-shadcn button

Install and integrate allauth component templates::

    just add-shadcn-allauth

Important template locations:

- ``django_template/templates/cotton`` for component templates
- ``django_template/templates/account`` for allauth pages
- ``django_template/templates/admin/login.html`` for custom admin login

Documentation Authoring
----------------------------------------------------------------------

Serve docs with Docker::

    docker compose -f docker-compose.docs.yml up --build

Legacy CLI alternative::

    docker-compose -f docker-compose.docs.yml up --build

Or run docs locally::

    cd docs
    uv run make livehtml

Generate API docs from docstrings::

    cd docs
    uv run make apidocs
