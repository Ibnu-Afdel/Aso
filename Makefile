APP_DIR=backend

setup:
	cp -n .env.example .env
	uv sync

HOST ?= 127.0.0.1
PORT ?= 8000

run: setup
	uv run --package backend uvicorn app.main:app --reload --host $(HOST) --port $(PORT)

MODULE_NAME := $(word 2,$(MAKECMDGOALS))

module:
	@if [ -z "$(name)" ] && [ -z "$(MODULE_NAME)" ]; then \
		echo "Usage: make module name=orders"; \
		echo "   or: make module orders"; \
		exit 1; \
	fi
	uv run --package backend fast make-module $(if $(name),$(name),$(MODULE_NAME))

%:
	@:

help:
	uv run --package backend fast help

shell:
	uv run --package backend ipython

lint:
	uv run --package backend ruff check backend

format:
	uv run --package backend ruff format backend

lint-fix:
	uv run --package backend ruff check --fix backend

docker-up:
	docker compose -f docker/docker-compose.yml up --build

docker-down:
	docker compose -f docker/docker-compose.yml down

migrate:
	uv run --package backend alembic -c $(APP_DIR)/alembic.ini upgrade head

revision:
	uv run --package backend alembic -c $(APP_DIR)/alembic.ini revision --autogenerate -m "init"

sync:
	uv sync
