export COMPOSE_FILE := "docker-compose.local.yml"

## Just does not yet manage signals for subprocesses reliably, which can lead to unexpected behavior.
## Exercise caution before expanding its usage in production environments.
## For more information, see https://github.com/casey/just/issues/2473 .


# Default command to list all available commands.
default:
    @just --list

# setup-local: Install Python dependencies.
setup-local:
    uv sync
    uv run python manage.py tailwind setup

# runserver: Run Django development server.
runserver:
    uv run python manage.py runserver

# check: Run Django system checks.
check:
    uv run python manage.py check --settings=config.settings.local

# migrate-shared: Apply shared schema migrations for django-tenants.
migrate-shared:
    uv run python manage.py migrate_schemas --shared

# migrate-tenants: Apply all tenant schema migrations.
migrate-tenants:
    uv run python manage.py migrate_schemas

# create-public-tenant: Create the public tenant and owner account.
create-public-tenant domain="localhost" owner="admin@example.com":
    uv run python manage.py create_public_tenant --domain_url {{domain}} --owner_email {{owner}}

# create-tenant-superuser: Create a superuser for a specific tenant schema.
create-tenant-superuser schema="public":
    uv run python manage.py create_tenant_superuser --schema {{schema}}

# test: Run pytest locally.
test *args:
    uv run pytest {{args}}

# typecheck: Run mypy checks.
typecheck:
    uv run mypy django_template

# tailwind-build: Build Tailwind CSS once.
tailwind-build:
    uv run python manage.py tailwind build

# tailwind-build-force: Force a clean Tailwind rebuild.
tailwind-build-force:
    uv run python manage.py tailwind build --force

# tailwind-setup: Download/configure the standalone Tailwind CLI binary.
tailwind-setup:
    uv run python manage.py tailwind setup

# add-shadcn: Add a single shadcn-django component.
add-shadcn component:
    uvx shadcn_django@latest add {{component}}

# add-shadcn-allauth: Add the allauth shadcn pack and sync generated templates.
add-shadcn-allauth:
    uvx shadcn_django@latest add allauth
    cp -f templates/account/*.html django_template/templates/account/
    cp -Rf templates/cotton/* django_template/templates/cotton/

# build: Build python image.
build *args:
    @echo "Building python image..."
    @docker compose build {{args}}

# up: Start up containers.
up:
    @echo "Starting up containers..."
    @docker compose up -d --remove-orphans

# down: Stop containers.
down:
    @echo "Stopping containers..."
    @docker compose down

# prune: Remove containers and their volumes.
prune *args:
    @echo "Killing containers and removing volumes..."
    @docker compose down -v {{args}}

# logs: View container logs
logs *args:
    @docker compose logs -f {{args}}

# manage: Executes `manage.py` command.
manage +args:
    @docker compose run --rm django python ./manage.py {{args}}

# pytest: Run tests with pytest.
pytest *args:
    @docker compose run --rm django pytest {{args}}

# tailwind-watch: Watch and rebuild Tailwind CSS on file changes.
tailwind-watch:
    uv run python manage.py tailwind watch

