# Telegram + FastAPI Modular Backend Template

[![Python](https://img.shields.io/badge/Python-3.11%2B-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111-green.svg)](https://fastapi.tiangolo.com)
[![aiogram](https://img.shields.io/badge/aiogram-3.x-blue.svg)](https://aiogram.dev)
[![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.0-red.svg)](https://www.sqlalchemy.org)
[![Docker](https://img.shields.io/badge/Docker-ready-2496ED.svg)](https://www.docker.com)

## Overview
This repository is an **opinionated backend template** for building:
- Telegram bots (aiogram v3)
- FastAPI APIs
- Telegram WebApps
- Modular monolith backends
- Docker-deployable services

It is designed for teams with a **Laravel / service-layer background** who want a clean, scalable Python architecture.

This template enforces:
- modular architecture
- separation of concerns
- async-first design
- production-ready patterns

This is **not** a starter for scripts. It is a **long-term backend foundation**.

## Philosophy
This template follows:
- Modular monolith
- Simple DDD
- Service layer architecture
- Async Python
- Clean separation between interface and logic

It is heavily inspired by Laravel structure but adapted to Python best practices.

## What this template IS
- A production-ready skeleton
- A scalable backend foundation
- A Telegram bot + API combo
- A modular architecture base
- A Docker-first project

## What this template is NOT
- Not a full SaaS starter
- Not a microservice system
- Not a heavy DDD enterprise setup
- Not a monolithic script bot

## Architecture Rules
- **Modules** contain pure business logic (no FastAPI, no aiogram, no Telegram objects).
- **Bot handlers** call services.
- **API routes** call services.
- **Services** call repositories.
- **Repositories** talk to the database.
- **Async** everywhere.

## Architecture Layers
| Layer | Location | Responsibility |
| --- | --- | --- |
| Interface | bot/, api/ | Receive input |
| Application | modules/*/service.py | Business logic |
| Domain | modules/*/models.py | Data models |
| Infrastructure | modules/*/repository.py | DB access |
| Core | core/ | Config, DB, logging |

## Request Flow Diagram (text)
```
Telegram → /bot/webhook → handler → service → repository → DB
HTTP     → /health      → route   → service → repository → DB
```

Modules never talk to Telegram directly.

## Architecture Diagram
```
┌───────────────────────────────┐
│           Telegram             │
└───────────────┬───────────────┘
                │
                ▼
┌───────────────────────────────┐
│          FastAPI App           │
│   /bot/webhook & /health       │
└───────────────┬───────────────┘
                │
                ▼
┌───────────────────────────────┐
│  Bot Handlers & API Routes     │
└───────────────┬───────────────┘
                │
                ▼
┌───────────────────────────────┐
│            Services            │
└───────────────┬───────────────┘
                │
                ▼
┌───────────────────────────────┐
│          Repositories          │
└───────────────┬───────────────┘
                │
                ▼
┌───────────────────────────────┐
│          PostgreSQL            │
└───────────────────────────────┘
```

## Folder Structure
| Path | Purpose |
| --- | --- |
| backend/app/main.py | FastAPI application entrypoint |
| backend/app/core | Settings, DB, logging, security |
| backend/app/modules | Business logic modules (includes users example) |
| backend/app/bot | aiogram dispatcher and handlers |
| backend/app/api | FastAPI routes and dependencies |
| backend/app/services | Shared services (skeleton) |
| backend/app/integrations | External integrations |
| backend/app/jobs | Background workers |
| backend/app/webapp | Telegram WebApp assets |
| backend/tests | Unit test folder (created day one) |
| backend/scripts | Admin and automation scripts |
| backend/alembic | Database migrations |
| docker | Dockerfile, compose, nginx config |
| .env.example | Environment template |

## Quick Start
### 1) Configure
```
cp .env.example .env
```
Set `TELEGRAM_BOT_TOKEN` and `TELEGRAM_WEBHOOK_URL`.

### 2) Install dependencies
```
make setup
```

### 3) Run (choose one)
```
make run
```
```
uv run --package backend python backend/app/main.py
```
If `TELEGRAM_BOT_TOKEN` or `TELEGRAM_WEBHOOK_URL` are missing, the app will fail fast with a Pydantic validation error.

## Fast CLI (code generation)
Run with:
```
make help
```
or:
```
uv run --package backend fast help
```

Create a module:
```
make module name=orders
```
or:
```
uv run --package backend fast make-module orders
```

## Module Structure
Each module contains:
```
modules/users/
  models.py
  schemas.py
  repository.py
  service.py
```
Modules contain business logic only.
Modules MUST NOT import:
- aiogram
- FastAPI Request
- Telegram objects

## Bot Layer Rules
Bot handlers:
- Receive message
- Call service
- Send response

Bot handlers must NOT:
- Query DB directly
- Contain business logic
- Implement payment logic
- Handle complex workflows

Bad:
```
handler → DB query
```

Good:
```
handler → service → repo
```

## API Layer Rules
Routes behave like Laravel controllers. They call services and must not contain business logic.

## Services Layer
Services contain business logic and orchestrate repositories, external APIs, and validation. They are reusable from bot, API, and jobs.

## Repository Layer
Repositories talk to the DB only. They must not call Telegram, send emails, or contain business logic.

## Red Line Rules (Important)
### DO NOT
- Import aiogram inside modules
- Put DB queries inside handlers
- Put business logic inside routes
- Call Telegram API from services
- Mix layers

### ALWAYS
- Handlers call services
- Services call repositories
- Modules stay pure
- Keep async everywhere

## Running Locally
1. Copy environment file:
   - `cp .env.example .env`
2. Set `TELEGRAM_BOT_TOKEN` and `TELEGRAM_WEBHOOK_URL`.
3. Install dependencies:
  - `make setup`
4. Start the app (choose one):
  - `make run`
  - `uv run --package backend python backend/app/main.py`

## Docker
- Build and run:
  - `make docker-up`
- Or directly:
  - `docker compose up --build`
- Stop:
  - `make docker-down`

Services:
- app
- postgres
- redis

## API Endpoints
| Method | Path | Description |
| --- | --- | --- |
| POST | /bot/webhook | Telegram webhook receiver |
| GET | /health | Health check |

## Migrations
- Create revision:
  - `make revision`
- Or directly:
  - `uv run --package backend alembic -c backend/alembic.ini revision --autogenerate -m "init"`
- Apply migrations:
  - `make migrate`
- Or directly:
  - `uv run --package backend alembic -c backend/alembic.ini upgrade head`

## Scripts
Useful automation lives in `backend/scripts/`:
- `set_webhook.py` (set Telegram webhook)
- `seed_data.py` (seed database)
- `admin_tasks.py` (admin tasks placeholder)

## How to Add a New Module
```
modules/products/
  models.py
  schemas.py
  repository.py
  service.py
```

Register models in metadata and keep the module pure.

## How to Add a Bot Handler
1. Create `backend/app/bot/handlers/<name>.py`.
2. Add a router and handler function.
3. Include the router in `backend/app/bot/dispatcher.py`.

Example:
```
bot/handlers/start.py
```

Handler must call service.

## Deployment Notes
- Use a public HTTPS URL for `TELEGRAM_WEBHOOK_URL`.
- Ensure `/bot/webhook` is reachable.
- Run migrations before starting the app.
- Use a production ASGI server (e.g., `uvicorn` behind a reverse proxy).
- Optional: use the provided Nginx config at `docker/nginx.conf`.

## AI Development Rules
When using AI agents, specify the layer to modify and enforce the module pattern.

Example prompt:
"Add feature inside modules/orders service layer only."

## Long-Term Scaling
This template supports a large modular monolith, easy microservice extraction, and team development.

## Final Notes
This template is intentionally opinionated. Consistency is more important than flexibility. Follow the rules strictly.

## Tech Stack
- **Python 3.11+**
- **FastAPI** (ASGI web framework)
- **aiogram v3** (Telegram bot framework)
- **SQLAlchemy 2.0** (async ORM)
- **PostgreSQL**
- **Docker**

## Configuration Reference
| Variable | Required | Description |
| --- | --- | --- |
| APP_NAME | ❌ | Application name |
| ENVIRONMENT | ❌ | Environment label (development/production) |
| DEBUG | ❌ | Debug mode |
| TELEGRAM_BOT_TOKEN | ✅ | Telegram bot token |
| TELEGRAM_WEBHOOK_URL | ✅ | Public webhook URL |
| DATABASE_URL | ✅ | Async SQLAlchemy database URL |
| REDIS_URL | ❌ | Redis URL |

## Useful Links
- FastAPI: https://fastapi.tiangolo.com
- aiogram: https://aiogram.dev
- SQLAlchemy: https://www.sqlalchemy.org
- PostgreSQL: https://www.postgresql.org
