# AI Contribution Rules

Non-negotiable rules for AI-assisted changes. **Read this before modifying code.**

## Request Flow (canonical)
```
handler/route → App Service (app/services/) → Module Service (app/modules/*/service.py) → Repository → DB
```

## Layer Responsibilities
| Layer | Location | Responsibility |
| --- | --- | --- |
| Interface | bot/, api/ | Receive input, call app services via Depends or injection |
| App boundary | services/ | Own session_scope, orchestrate module services + repos |
| Application | modules/*/service.py | Business logic (pure, no framework) |
| Domain | modules/*/models.py | Data models |
| Infrastructure | modules/*/repository.py | DB access only |
| Core | core/ | Config, DB, logging |

## Session Ownership
- **App services** use `session_scope(commit_on_exit=True)` from `app/core/db.py`.
- Repositories receive session from callers; they never create sessions or commit.
- Handlers and routes never touch DB or session directly.

## Naming Convention
- App boundary: `*AppService` (e.g. `UserAppService`) in `app/services/`
- Module logic: `*Service` (e.g. `UserService`) in `app/modules/*/service.py`

## Red Line Rules (Do Not Cross)
- Do **not** import aiogram inside `app/modules/*`.
- Do **not** put DB queries inside handlers or routes.
- Do **not** put business logic inside routes.
- Do **not** call Telegram API from module services.
- Do **not** mix layers.

## Adding a New App Service
1. Create `app/services/<name>.py` with `*AppService` using `session_scope(commit_on_exit=True)`.
2. Add `get_<name>_app_service()` in `app/bootstrap/container.py`.
3. API routes: use `Depends(get_<name>_app_service)`. Bot handlers: add to `ServiceInjectionMiddleware`, receive as handler param.

## Adding a New Bot Handler
1. Create `app/bot/handlers/<name>.py` with router.
2. In `app/bot/dispatcher.py`: `dp.include_router(<name>_router)`.
3. For services: add to `ServiceInjectionMiddleware` in `app/bot/middlewares/service_injection.py`, then receive as handler param.

## Adding a New Module (DB-backed)
1. `python manage.py make module <name>`.
2. **Add** `from app.modules.<name> import models as _<name>_models` to `alembic/env.py`.
3. Create migration: `python manage.py makemigration -m "add_<name>"`.
4. Add app service in `app/services/` that uses session_scope + module service + repository.

## When Modifying Code
- Choose a single layer and apply changes there.
- Use existing patterns (e.g. `UserAppService`, `UserService`) as reference.
