.PHONY: help install dev shell migrate makemigrations test lint clean docker-build docker-up docker-down

# Colors
GREEN  := $(shell tput -Txterm setaf 2)
YELLOW := $(shell tput -Txterm setaf 3)
RESET  := $(shell tput -Txterm sgr0)

help: ## Show this help
	@echo ''
	@echo 'Usage:'
	@echo '  ${YELLOW}make${RESET} ${GREEN}<target>${RESET}'
	@echo ''
	@echo 'Targets:'
	@awk 'BEGIN {FS = ":.*?## "} /^[a-zA-Z_-]+:.*?## / {printf "  ${YELLOW}%-20s${RESET} %s\n", $$1, $$2}' $(MAKEFILE_LIST)

# Python/Django Commands
install: ## Install dependencies
	pipenv install --dev



dev: ## Start development server
	pipenv run python manage.py runserver

shell: ## Open Django shell
	pipenv run python manage.py shell_plus

migrate: ## Run database migrations
	pipenv run python manage.py migrate

makemigrations: ## Create new migrations
	pipenv run python manage.py makemigrations

createsuperuser: ## Create admin user
	pipenv run python manage.py createsuperuser

collectstatic: ## Collect static files
	pipenv run python manage.py collectstatic --noinput

# Translation
makemessages: ## Update all translation files (ignore env)
	pipenv run python manage.py makemessages --all --ignore=env

compilemessages: ## Compile all translation files
	pipenv run python manage.py compilemessages

# Testing
test: ## Run tests
	pipenv run pytest

test-coverage: ## Run tests with coverage
	pipenv run pytest --cov=apps --cov-report=html

# Linting
lint: ## Run linters
	pipenv run ruff check .
	pipenv run ruff format --check .

lint-fix: ## Fix linting issues
	pipenv run ruff check --fix .
	pipenv run ruff format .

check: ## Run Django system checks
	pipenv run python manage.py check

# Celery
celery: ## Start Celery worker
	pipenv run celery -A apps.tasks worker -l info

celery-beat: ## Start Celery beat scheduler
	pipenv run celery -A apps.tasks beat -l info

# Clean
clean: ## Clean build artifacts
	find . -type f -name "*.pyc" -delete
	find . -type d -name "__pycache__" -delete
	rm -rf .pytest_cache htmlcov .coverage

# Docker Commands
docker-build: ## Build Docker images
	docker-compose build

docker-up: ## Start all services with Docker Compose
	docker-compose up -d

docker-up-tools: ## Start with optional tools (pgadmin, redis-commander)
	docker-compose --profile tools up -d

docker-down: ## Stop all Docker Compose services
	docker-compose down

docker-logs: ## View Docker Compose logs
	docker-compose logs -f

docker-shell: ## Open shell in backend container
	docker-compose exec backend bash

docker-migrate: ## Run migrations in Docker
	docker-compose exec backend python manage.py migrate

docker-createsuperuser: ## Create superuser in Docker
	docker-compose exec backend python manage.py createsuperuser

# Setup
setup: install ## Initial project setup
	pipenv run pre-commit install
	cp .env.example .env 2>/dev/null || true
	@echo "✅ Project setup complete!"
	@echo "Run 'make docker-up' to start services"
