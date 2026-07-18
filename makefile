.PHONY: up down restart logs

COMPOSE=docker-compose --project-directory . -f infra/docker-compose.yml
ENV_FILE ?= .env

up:
	$(COMPOSE) --env-file $(ENV_FILE) up -d --build

down:
	$(COMPOSE) down

restart:
	$(COMPOSE) down
	$(COMPOSE) up -d django celery redis

logs:
	$(COMPOSE) logs -f django celery redis

	
