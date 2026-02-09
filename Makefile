APP_DIR=backend

setup:
	cp -n .env.example .env
	uv sync

run: setup
	uv run --package backend uvicorn app.main:app --reload --host 127.0.0.1 --port 8000

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
