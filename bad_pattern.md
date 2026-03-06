# Demo Development Notes: Patterns Observed

Observations while building the Note Keeper Bot. Updated after each development step.

---

## Bot: Note Keeper Bot

**Features:**
- `/start` — Register user, welcome
- `/help` — List commands
- `/note <text>` — Save a note (one per user, overwrites)
- `/mynote` — Show saved note
- `/webapp` — Button to open HTML/JS WebApp (view/edit note via API)

**Why:** Touches module, app service, handlers, middleware, API routes, static serving, WebApp. Full template flow.

---

## Step 1: DB Config (fastapi/password)

**Changed:** docker-compose.yml, .env.example, app/core/config.py

**Good:**
- Single place (config.py) for default DB URL
- docker-compose env vars match DATABASE_URL

**Observation:** Default config uses `db` hostname—only works inside Docker. Local dev needs `localhost`. .env.example documents both.

---

## Step 2: `make module notes`

**Good:**
- CLI printed exact next steps (alembic import, makemigration)
- Generated module matches AGENTS.md layout
- No manual file creation

**Observation:** Generated repository/service were minimal; had to customize for get_by_user_id, create, update. The scaffolder is a starting point, not full CRUD.

---

## Step 3: Notes Module (models, repo, service, schemas)

**Files:** app/modules/notes/*.py

**Good:**
- No aiogram/FastAPI imports in module
- Repository receives session, never commits
- Service is pure orchestration over repo
- FK to users.id for referential integrity

**Potential bad:**
- Note.user_id uses users.id (internal). Handlers work with telegram_id. App service must resolve via UserAppService.ensure_user(). Clear separation.

---

## Step 4: NotesAppService + Container + Middleware

**Files:** app/services/notes.py, app/bootstrap/container.py, app/bot/middlewares/service_injection.py

**Good:**
- session_scope(commit_on_exit=True) for write; commit_on_exit=False for read-only
- Container getter pattern: add global, add get_X_app_service()
- Middleware: add data["notes_app_service"] = get_notes_app_service()
- Handler receives notes_app_service as param (aiogram DI)

**Repetition:** Each new app service = 5 lines in container + 1 line in middleware. Documented in AGENTS.md.

---

## Step 5: Handlers (start, help, note, mynote, webapp)

**Files:** app/bot/handlers/*.py

**Good:**
- Handlers thin: parse input, call services, send response
- Multi-service handlers: user_app_service + notes_app_service
- Resolve telegram_id → user.id in handler via ensure_user
- No DB access in handlers

**Pattern:** For operations needing user_id (internal), call ensure_user(telegram_id) first, then use user.id.

---

## Step 6: API Routes + WebApp (HTML/JS)

**Files:** app/api/routes/webapp.py, app/core/telegram_webapp.py, app/webapp/*

**Good:**
- Depends(_get_telegram_user_id) for auth
- initData validation (HMAC) before trusting user
- API uses same app services as bot
- StaticFiles mount for /static
- HTML page at /webapp

**Potential bad:**
- WEBAPP_URL: Telegram WebApp requires HTTPS in production. localhost works for some testing.
- initData validation is required for production; demo uses it.

---

## Step 7: Alembic Migration

**Observation:** `context.run_async_migrations` not in older Alembic. Replaced with `asyncio.run(run_migrations_online())`. Manual migration file created when autogenerate failed (missing script.py.mako).

---

## Red Lines (Avoided)

| Rule | How we complied |
|------|-----------------|
| No aiogram in modules | notes module has none |
| No DB in handlers | Handlers call app services only |
| No business logic in routes | Routes call app services |
| Repositories never commit | Only flush; app service owns commit |
| Services from container only | All via get_*_app_service() |

---

## Best Patterns Used

1. **Handler → App Service → Module Service → Repo** — Clear flow
2. **session_scope in app services only** — Single place for transaction boundaries
3. **Depends() for API** — FastAPI idiomatic
4. **Middleware injection for bot** — aiogram idiomatic
5. **initData validation** — Security for WebApp
6. **Config for webapp_url** — Environment-specific URLs

---

## Files Touched (Summary)

- `app/modules/notes/` — models, repository, service, schemas
- `app/services/notes.py` — NotesAppService
- `app/bootstrap/container.py` — get_notes_app_service
- `app/bot/middlewares/service_injection.py` — notes_app_service
- `app/bot/handlers/start.py` — help
- `app/bot/handlers/notes.py` — note, mynote
- `app/bot/handlers/webapp.py` — webapp
- `app/bot/dispatcher.py` — include routers
- `app/api/routes/webapp.py` — GET/POST note, serve HTML
- `app/core/telegram_webapp.py` — initData validation
- `app/main.py` — webapp router, static mount
- `app/webapp/templates/webapp.html`, `app/webapp/static/webapp.js`
- `alembic/env.py` — notes models import, asyncio.run fix
- `alembic/versions/001_add_users_and_notes.py`
- `app/core/config.py` — webapp_url
- `docker/docker-compose.yml`, `.env.example`
- `tests/architecture/test_service_instantiation.py` — NotesAppService
- `app/api/deps.py` — get_notes_app_service

---

## Process Rating by Developer Level

| Level | Rating (1–5) | Notes |
|-------|--------------|-------|
| **Beginner** | 2/5 | Too many concepts at once: layers, sessions, DI, middleware. Many files to touch. Easy to put code in wrong place. Needs hand-holding. |
| **Intermediate** | 4/5 | Can follow if they read AGENTS.md. Structure is clear once understood. Some repetition (container + middleware per service). Good fit with docs. |
| **Pro** | 5/5 | Quick to grasp. Appreciates separation. Might want less boilerplate. Smooth once patterns are internalized. |
| **Vibecoder** | 1–2/5 | Doesn't read code. Relies on AI. Success = "I ask AI, it does the right thing." High risk AI puts code in wrong layer. Needs strong rules + minimal ambiguity. |

---

## Future: Optimizing for Beginner → Vibecoder

Most future users will be beginners, intermediates, or vibecoders. Here’s what can make the template work better for them.

### 1. One-shot feature scaffolding

- **Problem:** Adding a feature = touch 10+ files (module, service, container, middleware, handlers, routes).
- **Solution:** `make feature notes` or `python manage.py scaffold notes` that generates module + app service + handlers + API route in one go.
- **Impact:** Vibecoder says "add notes" → one command → done.

### 2. Stronger AI rules (cursor rules, AGENTS.md)

- **Problem:** AI can put DB in handlers, aiogram in modules, or skip layers.
- **Solution:** Very explicit rules with examples of "DO" and "DON'T" per file. File-specific rules (e.g. `.cursor/rules/handlers.mdc`: "handlers only call services, never import db").
- **Impact:** AI stays within the architecture even when the user doesn’t know it.

### 3. Vibecoder onboarding prompt

- **Problem:** Vibecoder doesn’t know what to tell AI.
- **Solution:** A short `VIBECODER.md` or prompt template: "Describe your feature in plain English. AI will ask 1–2 clarifying questions. Answer. Done."
- **Impact:** Clear mental model and predictable flow.

### 4. Reduce boilerplate per feature

- **Problem:** Each new app service = 5 lines container + 1 middleware + register in deps.
- **Solution:** Convention over config: e.g. auto-register services from a `services/` folder, or a decorator that wires injection.
- **Impact:** Fewer files/lines to touch = fewer chances to break.

### 5. Layered flow diagram (in docs)

- **Problem:** Beginners don’t know "where does this go?"
- **Solution:** A simple diagram: User → Handler → App Service → Module → Repo → DB. With file paths next to each box.
- **Impact:** Visual answer to "I want X, where do I put it?"

### 6. Better error messages when rules are broken

- **Problem:** Putting DB in a handler "works" until things get messy.
- **Solution:** Architecture tests that fail with clear messages, e.g. "Handlers must not import from app.core.db. Found in app/bot/handlers/notes.py."
- **Impact:** Immediate feedback instead of hidden debt.

### 7. Batteries-included defaults

- **Problem:** Vibecoder has to set DATABASE_URL, TELEGRAM_BOT_TOKEN, etc.
- **Solution:** Sensible defaults, `manage.py run` that checks env and prints "Set X in .env" if missing. Optional `manage.py demo` that runs a minimal setup.
- **Impact:** Fewer setup steps, fewer ways to fail.

### Priority for vibecoders

1. **Strong AI rules** — Highest impact. AI does the right thing even when the user doesn’t.
2. **One-shot scaffolding** — Fewer manual steps.
3. **Vibecoder prompt / onboarding** — Clear expectations.
4. **Error messages** — Catch mistakes early.
5. **Flow diagram** — Quick mental model.
6. **Less boilerplate** — Less surface area for mistakes.
7. **Defaults** — Smoother first run.
