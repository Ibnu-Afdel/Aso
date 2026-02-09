APP_DIR=backend

run:
	cd $(APP_DIR) && uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

docker-up:
	docker compose -f docker/docker-compose.yml up --build

docker-down:
	docker compose -f docker/docker-compose.yml down

migrate:
	cd $(APP_DIR) && alembic upgrade head

revision:
	cd $(APP_DIR) && alembic revision --autogenerate -m "init"
