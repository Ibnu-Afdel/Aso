# FastGram

[![Python](https://img.shields.io/badge/Python-3.11%2B-blue.svg)](https://python.org)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.111-green.svg)](https://fastapi.tiangolo.com)
[![aiogram](https://img.shields.io/badge/aiogram-3.x-blue.svg)](https://aiogram.dev)
[![SQLAlchemy](https://img.shields.io/badge/SQLAlchemy-2.0-red.svg)](https://www.sqlalchemy.org)
[![PyPI](https://img.shields.io/badge/PyPI-fastogram-orange.svg)](https://pypi.org/project/fastogram)

**Production-grade Python backend starter kit for Telegram bots + FastAPI.**  
Clean architecture enforced by tests. Async-first. Docker-ready.

---

## Get started

```bash
pip install fastogram
fastogram new my-bot
cd my-bot
cp .env.example .env   # set TELEGRAM_BOT_TOKEN
python manage.py demo  # setup + migrate + run
```

That's it. Your bot is running.

### fastogram CLI options

```bash
fastogram new my-bot              # create ./my-bot/
fastogram new .                   # scaffold into current directory
fastogram new . --force           # scaffold into a non-empty directory
fastogram new my-bot -d ~/code    # create ~/code/my-bot/
```

---

## What is FastGram

FastGram is an opinionated backend template for building **modular monolith applications** that combine a Telegram bot and a REST API in a single Python service.

It is not a script starter. It is a **long-term backend foundation** — the kind you clone once and build a real product on top of. It enforces clean architecture through automated tests that run on every commit. If you break a rule, CI fails.

Designed for teams with a **Laravel or Django background** who want the same kind of structure in Python.

---

## Tech Stack

| Layer | Tool | Purpose |
|---|---|---|
| HTTP API | **FastAPI** | Async web framework |
| Telegram bot | **aiogram 3** | Async Telegram bot framework |
| ORM | **SQLAlchemy 2.0** (async) | Database access |
| Migrations | **Alembic** | Schema migrations (autogenerate) |
| Database | **PostgreSQL** | Primary data store |
| Cache / rate limit | **Redis** | Optional, for multi-worker rate limiting |
| Logging | **Loguru** | Structured JSON logs in prod, colored in dev |
| Config | **Pydantic Settings** | Typed env var validation |
| Runtime | **Docker + uvicorn** | Containerized deployment |
| CLI | **Typer** | `manage.py` command hub |
| Linting | **Ruff** | Fast linter + formatter |

---

## Architecture

FastGram enforces a strict 4-layer model. Every request flows in one direction:

```
Interface → App Service → Module Service → Repository → DB

bot/handlers/       app/services/       app/modules/*/      app/modules/*/
app/api/routes/     (owns session)      service.py          repository.py
```

### Layer responsibilities

| Layer | Location | Responsibility |
|---|---|---|
| **Interface** | `app/bot/handlers/`, `app/api/routes/` | Receive input, call app services |
| **App boundary** | `app/services/` | Own `session_scope`, orchestrate module services + repos |
| **Application** | `app/modules/*/service.py` | Pure business logic — no framework imports |
| **Domain** | `app/modules/*/models.py` | SQLAlchemy models |
| **Infrastructure** | `app/modules/*/repository.py` | DB queries only — no commits |
| **Core** | `app/core/` | Config, DB engine, logging, security |

### The rules (enforced by tests)

These are not guidelines. If you violate them, **tests fail and CI blocks the merge.**

| Rule | What it prevents |
|---|---|
| No aiogram/FastAPI imports inside `app/modules/` | Framework lock-in in business logic |
| No DB queries in handlers or routes | Skipping the service layer |
| Services created only via `app/bootstrap/container.py` | Hidden singletons, test bypasses |
| `session_scope` only in `app/services/` | Ambiguous transaction boundaries |
| Only app services commit | Repositories committing mid-transaction |

Architecture guard tests live in `tests/architecture/` and run on every commit via pre-commit hooks.

### Request flow

```
Telegram update → /bot/webhook → handler → UserAppService → UserService → UserRepository → DB
HTTP request    → /api/route   → route   → AppService     → ModuleService → Repository   → DB
```

---

## Project Structure

```
app/
├── main.py                    # FastAPI app, lifespan, webhook route
├── core/
│   ├── config.py              # Pydantic Settings (reads .env)
│   ├── db.py                  # Async engine, session_scope, Base
│   └── security.py
├── bootstrap/
│   ├── container.py           # Centralized DI — all services created here
│   ├── logging.py             # Dev (colored) / prod (JSON) log config
│   ├── request_id_middleware.py
│   ├── request_context.py
│   └── startup_checks.py      # Prod safety: env vars, DB, alembic head
├── bot/
│   ├── dispatcher.py          # aiogram setup, middleware stack
│   ├── handlers/start.py      # /start command (reference implementation)
│   └── middlewares/
│       ├── service_injection.py   # Injects app services into handlers
│       ├── error_logging.py
│       └── rate_limit.py          # Per-user rate limiting
├── api/
│   ├── routes/health.py       # /healthz, /readyz
│   └── deps.py
├── modules/
│   └── users/                 # Reference module
│       ├── models.py          # SQLAlchemy User model
│       ├── schemas.py         # Pydantic DTOs
│       ├── repository.py      # DB queries (no commits)
│       └── service.py         # Business logic (no framework imports)
├── services/
│   ├── users.py               # UserAppService — owns session + orchestration
│   ├── health.py              # HealthAppService — liveness + readiness
│   └── telegram_webhook.py
├── integrations/telegram.py   # Webhook setup/teardown
├── jobs/worker.py             # Background worker stub
└── webapp/                    # Static files + templates

tests/
├── architecture/              # Guard tests — enforce layering rules
├── integration/               # Real DB tests (SQLite in-memory)
└── test_*.py                  # Config, request ID, startup check tests

alembic/
├── env.py                     # Async alembic config
└── versions/                  # Migration files (autogenerated)

docker/
├── Dockerfile
└── docker-compose.yml         # app + postgres + redis

manage.py                      # Primary CLI
.env.example                   # Environment template
```

---

## manage.py Commands

Your primary interface for everything:

```bash
python manage.py --help
```

| Command | Description |
|---|---|
| `demo` | Setup + migrate + run. One command to get going. |
| `bootstrap` | Setup + migrate (without running). Then `run`. |
| `run` | Start the app with uvicorn. |
| `setup` | Create `.env` from example, install deps. |
| `test` | Run the full test suite. |
| `lint` | Ruff lint. Add `--fix` to auto-fix. |
| `format` | Ruff format. |
| `check` | Lint + format + architecture tests. |
| `shell` | IPython shell with app context. |
| `doctor` | Check env, DB connectivity, migration state. |
| `migrate` | Apply pending Alembic migrations. |
| `makemigration -m "desc"` | Autogenerate a new migration from model changes. |
| `make module <name>` | Scaffold a new module (models, schemas, repo, service). |
| `docker-up` | Start Docker services (app + postgres + redis). |
| `docker-down` | Stop Docker services. |

---

## Adding a New Module

This is the core workflow. Every feature lives in a module.

### 1. Scaffold

```bash
python manage.py make module orders
```

Creates `app/modules/orders/` with stub files.

### 2. Define the model (`app/modules/orders/models.py`)

```python
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import BigInteger, String
from app.core.db import Base

class Order(Base):
    __tablename__ = "orders"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    user_id: Mapped[int] = mapped_column(BigInteger)
    status: Mapped[str] = mapped_column(String(50))
```

### 3. Write the repository (`app/modules/orders/repository.py`)

Receives a session. Never commits.

```python
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.modules.orders.models import Order

class OrderRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, user_id: int) -> Order:
        order = Order(user_id=user_id, status="pending")
        self._session.add(order)
        await self._session.flush()
        return order
```

### 4. Write the domain service (`app/modules/orders/service.py`)

Pure logic. No framework imports.

```python
from app.modules.orders.repository import OrderRepository

class OrderService:
    def __init__(self, repo: OrderRepository) -> None:
        self._repo = repo

    async def place_order(self, user_id: int):
        return await self._repo.create(user_id=user_id)
```

### 5. Write the app service (`app/services/orders.py`)

Owns the session and transaction.

```python
from app.core.db import session_scope
from app.modules.orders.repository import OrderRepository
from app.modules.orders.service import OrderService

class OrderAppService:
    async def place_order(self, user_id: int):
        async with session_scope(commit_on_exit=True) as session:
            repo = OrderRepository(session)
            svc = OrderService(repo)
            return await svc.place_order(user_id=user_id)
```

### 6. Register in container (`app/bootstrap/container.py`)

```python
from app.services.orders import OrderAppService

_order_app_service: OrderAppService | None = None

def get_order_app_service() -> OrderAppService:
    global _order_app_service
    if _order_app_service is None:
        _order_app_service = OrderAppService()
    return _order_app_service
```

### 7. Use in a bot handler or API route

**Bot handler:**
```python
@router.message(Command("order"))
async def order_handler(message: Message, order_app_service: OrderAppService):
    order = await order_app_service.place_order(user_id=message.from_user.id)
    await message.answer(f"Order #{order.id} placed.")
```

**API route:**
```python
@router.post("/orders")
async def create_order(svc: OrderAppService = Depends(get_order_app_service)):
    return await svc.place_order(user_id=...)
```

### 8. Register model in alembic + migrate

In `alembic/env.py`, add:
```python
from app.modules.orders import models as _orders_models  # noqa: F401
```

Then:
```bash
python manage.py makemigration -m "add orders table"
python manage.py migrate
```

---

## Bot Delivery Modes

Set in `.env`:

```env
TELEGRAM_DELIVERY_MODE=polling   # default — local dev, no public URL needed
TELEGRAM_DELIVERY_MODE=webhook   # production — requires TELEGRAM_WEBHOOK_URL
```

Polling starts automatically on app boot. Webhook receives updates at `/bot/webhook`.

### Webhook security

Set `TELEGRAM_WEBHOOK_SECRET` in `.env`. FastGram validates the `X-Telegram-Bot-Api-Secret-Token` header on every incoming update and returns 403 if it doesn't match.

---

## Health Endpoints

| Endpoint | Status | Meaning |
|---|---|---|
| `GET /healthz` | 200 always | App is alive |
| `GET /readyz` | 200 / 503 | DB is reachable / unreachable |

Use `/healthz` for liveness probes and `/readyz` for readiness probes in Kubernetes or any container orchestrator.

---

## Rate Limiting

Bot messages are rate-limited per user. Configure in `.env`:

```env
RATE_LIMIT_BACKEND=memory   # single process (default)
RATE_LIMIT_BACKEND=redis    # multi-worker (requires REDIS_URL)
RATE_LIMIT_PER_MINUTE=30    # default
```

---

## Observability

**Structured logging** via Loguru. Every log line in production is JSON:

```json
{"level": "INFO", "event_type": "request", "request_id": "abc123", "path": "/bot/webhook", "method": "POST"}
```

Dev mode: colored, human-readable output.

**Request correlation**: every request gets a UUID (`X-Request-ID` header, included in all log lines).

**Startup checks** (production only): on boot, FastGram validates required env vars, DB connectivity, and that migrations are at the Alembic head. Fails fast if anything is wrong — no silent broken deployments.

---

## Configuration Reference

| Variable | Required | Default | Description |
|---|---|---|---|
| `TELEGRAM_BOT_TOKEN` | ✅ | — | From [@BotFather](https://t.me/BotFather) |
| `DATABASE_URL` | ✅ | postgres://... | Async SQLAlchemy URL (`postgresql+asyncpg://...`) |
| `TELEGRAM_DELIVERY_MODE` | ❌ | `polling` | `polling` or `webhook` |
| `TELEGRAM_WEBHOOK_URL` | ⚠️ | — | Required when delivery mode is `webhook` |
| `TELEGRAM_WEBHOOK_SECRET` | ❌ | — | Validates incoming webhook requests |
| `BOT_ENABLED` | ❌ | `true` | Set `false` to run API only (no token required) |
| `ENVIRONMENT` | ❌ | `production` | `development` disables startup checks |
| `DEBUG` | ❌ | `false` | Includes stack traces in error responses |
| `REDIS_URL` | ❌ | redis://redis:6379 | Required when `RATE_LIMIT_BACKEND=redis` |
| `RATE_LIMIT_BACKEND` | ❌ | `memory` | `memory` or `redis` |
| `RATE_LIMIT_PER_MINUTE` | ❌ | `30` | Max bot messages per user per minute |

---

## Deployment

1. Set `ENVIRONMENT=production` in your env.
2. Set `TELEGRAM_DELIVERY_MODE=webhook` and `TELEGRAM_WEBHOOK_URL=https://your-domain.com/bot/webhook`.
3. Run migrations before starting: `python manage.py migrate`.
4. Start with uvicorn behind a reverse proxy (nginx config included in `docker/`).
5. FastGram will fail fast on boot if migrations are not applied — safe for rolling deploys.

```bash
docker compose up --build
```

---

## AI-assisted development

FastGram is designed to work well with AI coding assistants. See `AGENTS.md` for the full rule set.

Quick prompts that work:

- `"Add a notes feature: users can save one note via /note <text> and read it with /mynote"`
- `"Add a GET /api/notes route that returns the current user's notes"`
- `"Add rate limiting to the /order command — max 3 per minute"`

The architecture guard tests catch AI mistakes before they reach code review.

---

## Contributing and extending

See `CONTRIBUTING.md` for the full module workflow and architecture rules.

---

## Links

- **PyPI**: `pip install fastogram` → [pypi.org/project/fastogram](https://pypi.org/project/fastogram)
- **FastAPI**: [fastapi.tiangolo.com](https://fastapi.tiangolo.com)
- **aiogram**: [aiogram.dev](https://aiogram.dev)
- **SQLAlchemy**: [sqlalchemy.org](https://www.sqlalchemy.org)
