setup:
	cp -n .env.example .env
	uv sync

HOST ?= 127.0.0.1
PORT ?= 8000

run: setup
	uv run uvicorn app.main:app --reload --host $(HOST) --port $(PORT)

MODULE_NAME := $(word 2,$(MAKECMDGOALS))

module:
	@if [ -z "$(name)" ] && [ -z "$(MODULE_NAME)" ]; then \
		echo "Usage: make module name=orders"; \
		echo "   or: make module orders"; \
		exit 1; \
	fi
	uv run fast make-module $(if $(name),$(name),$(MODULE_NAME))

%:
	@:

help:
	uv run fast help

shell:
	uv run ipython

lint:
	uv run ruff check app tests

format:
	uv run ruff format app tests

lint-fix:
	uv run ruff check --fix app tests

docker-up:
	docker compose -f docker/docker-compose.yml up --build

docker-down:
	docker compose -f docker/docker-compose.yml down

migrate:
	uv run alembic -c alembic.ini upgrade head

revision:
	uv run alembic -c alembic.ini revision --autogenerate -m "init"

sync:
	uv sync
