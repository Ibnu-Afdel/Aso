# Telegram FastAPI Template

## Overview
A production-ready but minimal monolith template for Telegram bots and FastAPI applications using aiogram v3, async SQLAlchemy, and PostgreSQL. It follows a Laravel-inspired modular layout and a simple DDD-inspired layering: handlers/routes → services → repositories → database.

## Architecture
- **Modules** contain pure business logic (no FastAPI, no aiogram, no Telegram objects).
- **Bot handlers** call services.
- **API routes** call services.
- **Services** call repositories.
- **Repositories** talk to the database.
- **Async** everywhere.

### Request Flow Diagram (text)
```
Telegram -> /bot/webhook -> Handler -> Service -> Repository -> DB
HTTP     -> /health      -> Route   -> Service -> Repository -> DB
```

## Folder Structure
| Path | Purpose |
|---|---|
| backend/app/main.py | FastAPI application entrypoint |
| backend/app/core | Settings, DB, logging, security |
| backend/app/modules | Business logic modules |
| backend/app/bot | aiogram dispatcher and handlers |
| backend/app/api | FastAPI routes and dependencies |
| backend/app/services | Shared service layer (skeleton) |
| backend/app/integrations | External service integrations |
| backend/app/jobs | Background job workers |
| backend/app/webapp | Web UI assets (optional) |
| backend/alembic | Database migrations |
| docker | Dockerfile and docker-compose |

## Running Locally
1. Copy environment file:
   - `cp .env.example .env`
2. Set `TELEGRAM_BOT_TOKEN` and `TELEGRAM_WEBHOOK_URL`.
3. Install dependencies:
   - `cd backend && uv pip install -r requirements.txt`
4. Start the app:
   - `make run`

## Docker Usage
- Build and run:
  - `make docker-up`
- Stop:
  - `make docker-down`

## Migrations
- Create revision:
  - `make revision`
- Apply migrations:
  - `make migrate`

## How to Create a Module
1. Create a folder under `backend/app/modules/<module_name>`.
2. Add `models.py`, `repository.py`, and `service.py`.
3. Keep modules pure (no FastAPI/aiogram imports).
4. Call the service from routes/handlers.

## How to Add a Bot Handler
1. Create `backend/app/bot/handlers/<name>.py`.
2. Add a router and handler function.
3. Include the router in `backend/app/bot/dispatcher.py`.

## Deployment Notes
- Use a public HTTPS URL for `TELEGRAM_WEBHOOK_URL`.
- Ensure the `/bot/webhook` endpoint is reachable.
- Run migrations before starting the app.
- Use a production ASGI server (e.g., `uvicorn` behind a reverse proxy).
