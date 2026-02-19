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

## Code Flow (Where to Put Things)
```
Handler/Route          App Service           Module                 Repo
app/bot/handlers/  →   app/services/     →   app/modules/*/service  →  app/modules/*/repository.py
app/api/routes/        (session_scope)       (business logic)          (DB access only)

Example: /note <text>
  handlers/notes.py  →  services/notes.py  →  modules/notes/service.py  →  modules/notes/repository.py
```

## Folder Structure
| Path | Purpose |
| --- | --- |
| app/main.py | FastAPI application entrypoint |
| app/core | Settings, DB, logging, security |
| app/modules | Business logic modules (includes users example) |
| app/bot | aiogram dispatcher and handlers |
| app/api | FastAPI routes and dependencies |
| app/services | Shared services (skeleton) |
| app/integrations | External integrations |
| app/jobs | Background workers |
| app/webapp | Telegram WebApp assets |
| tests | Unit test folder (created day one) |
| scripts | Admin and automation scripts |
| alembic | Database migrations |
| docker | Dockerfile, compose, nginx config |
| .env.example | Environment template |

## Quick Start

### Fastest (one command)
```bash
cp .env.example .env   # edit .env: set TELEGRAM_BOT_TOKEN
python manage.py demo  # setup + migrate + run
```

### Step by step
1. Configure:
   ```bash
   cp .env.example .env
   ```
   Set `TELEGRAM_BOT_TOKEN`. If using webhook mode, also set `TELEGRAM_DELIVERY_MODE=webhook` and `TELEGRAM_WEBHOOK_URL`.

2. Install dependencies:
   ```bash
   python manage.py setup
   ```

3. Run (choose one):
   ```bash
   python manage.py run --reload
   ```
   ```bash
   uv run uvicorn app.main:app --reload
   ```

If `TELEGRAM_BOT_TOKEN` is missing, the app will fail fast with a Pydantic validation error.
`TELEGRAM_WEBHOOK_URL` is required only when `TELEGRAM_DELIVERY_MODE=webhook`.

## Manage Commands
View all commands:
```bash
python manage.py --help
```

| Command | Description |
| --- | --- |
| `demo` | Setup + migrate + run. One command to get going. |
| `bootstrap` | Setup + migrate. Prepares project; then `run`. |
| `run` | Start the app (uvicorn). |
| `setup` | Create .env from example, install deps. |
| `migrate` | Apply DB migrations. |
| `make module <name>` | Scaffold a new module. |
| `lint`, `format`, `test` | Code quality. |
| `docker-up`, `docker-down` | Docker compose. |

## Fast CLI (code generation)
Create a module:
```bash
python manage.py make module orders
```
or:
```
uv run fast make-module orders
```

## Developer Tools
Lint and format (Ruff):
```
python manage.py lint
python manage.py lint --fix
python manage.py format
```

Interactive shell (IPython):
```
python manage.py shell
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
2. Set `TELEGRAM_BOT_TOKEN`.
   For webhook mode, set `TELEGRAM_DELIVERY_MODE=webhook` and `TELEGRAM_WEBHOOK_URL`.
3. Install dependencies:
  - `python manage.py setup`
4. Start the app (choose one):
  - `python manage.py run --reload`
  - `uv run uvicorn app.main:app --reload`

### Run Options (Host/Port)
Defaults:
- `HOST=127.0.0.1`
- `PORT=8000`

Examples:
```
python manage.py run --port 8001
python manage.py run --host 0.0.0.0
python manage.py run --host 0.0.0.0 --port 9000
```

## Docker
- Build and run:
  - `python manage.py docker-up`
- Or directly:
  - `docker compose up --build`
- Stop:
  - `python manage.py docker-down`

Services:
- app
- postgres
- redis

## API Endpoints
| Method | Path | Description |
| --- | --- | --- |
| POST | /bot/webhook | Telegram webhook receiver |
| GET | /health | Health check |

## Telegram Delivery Mode
- `polling` (default): best for local development, no public URL needed.
- `webhook`: production mode, requires `TELEGRAM_WEBHOOK_URL`.

Examples:
- Polling (default): set `TELEGRAM_BOT_TOKEN`, keep `TELEGRAM_DELIVERY_MODE=polling`.
- Webhook: set `TELEGRAM_DELIVERY_MODE=webhook` and
  `TELEGRAM_WEBHOOK_URL=https://your-domain.com/bot/webhook`.

## Migrations
- Create revision:
  - `python manage.py makemigration -m "init"`
- Or directly:
  - `uv run alembic -c alembic.ini revision --autogenerate -m "init"`
- Apply migrations:
  - `python manage.py migrate`
- Or directly:
  - `uv run alembic -c alembic.ini upgrade head`

## Scripts
Useful automation lives in `scripts/`:
- `set_webhook.py`:
  - set webhook: `uv run python -m scripts.set_webhook`
  - delete webhook: `uv run python -m scripts.set_webhook --delete`
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
1. Create `app/bot/handlers/<name>.py`.
2. Add a router and handler function.
3. Include the router in `app/bot/dispatcher.py`.

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
This template is optimized for AI-assisted development. See `AGENTS.md` for full rules.

**Layer-specific prompts:**
- "Add a new module `products`: `python manage.py make module products`, then add to alembic/env.py"
- "Add business logic in `app/modules/users/service.py` only — no handlers, no DB in routes"
- "Add new API route in `app/api/routes/`, use `Depends(get_*_app_service)`"
- "Add bot handler in `app/bot/handlers/`, receive services via ServiceInjectionMiddleware"

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
| TELEGRAM_DELIVERY_MODE | ❌ | `polling` (default) or `webhook` |
| TELEGRAM_WEBHOOK_URL | ⚠️ | Required only for `TELEGRAM_DELIVERY_MODE=webhook` |
| DATABASE_URL | ✅ | Async SQLAlchemy database URL |
| REDIS_URL | ❌ | Redis URL |
| RATE_LIMIT_BACKEND | ❌ | `memory` (default) or `redis` for bot rate limiting |
| RATE_LIMIT_PER_MINUTE | ❌ | Max bot messages per user per minute (default 30) |

## Useful Links
- FastAPI: https://fastapi.tiangolo.com
- aiogram: https://aiogram.dev
- SQLAlchemy: https://www.sqlalchemy.org
- PostgreSQL: https://www.postgresql.org
