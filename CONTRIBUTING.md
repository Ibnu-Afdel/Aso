# Contributing to FastGram

## Adding a new module

FastGram uses a strict four-layer architecture enforced by automated tests. Here is the complete workflow for adding a new feature module.

### 1. Scaffold the module

```bash
python manage.py make module <name>
```

This creates `app/modules/<name>/` with stub files for models, schemas, repository, and service.

### 2. Define your model (`app/modules/<name>/models.py`)

```python
from sqlalchemy.orm import Mapped, mapped_column
from sqlalchemy import BigInteger
from app.core.db import Base

class MyModel(Base):
    __tablename__ = "my_models"
    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
```

### 3. Define schemas (`app/modules/<name>/schemas.py`)

Pydantic models used as DTOs between layers. No SQLAlchemy imports here.

### 4. Write the repository (`app/modules/<name>/repository.py`)

Receives a session from the caller. Never commits or rolls back — only flushes.

```python
from sqlalchemy.ext.asyncio import AsyncSession

class MyModelRepository:
    def __init__(self, session: AsyncSession) -> None:
        self._session = session
```

### 5. Write the domain service (`app/modules/<name>/service.py`)

Pure business logic. No framework imports (FastAPI, aiogram). Receives its repository from the caller.

```python
from app.modules.<name>.repository import MyModelRepository

class MyModelService:
    def __init__(self, repo: MyModelRepository) -> None:
        self._repo = repo
```

### 6. Write the app service (`app/services/<name>.py`)

This is the session owner. It opens `session_scope`, wires the repo and domain service, and calls through. One `session_scope` per use-case method.

```python
from app.core.db import session_scope
from app.modules.<name>.repository import MyModelRepository
from app.modules.<name>.service import MyModelService

class MyModelAppService:
    async def do_thing(self, ...):
        async with session_scope(commit_on_exit=True) as session:
            repo = MyModelRepository(session)
            svc = MyModelService(repo)
            return await svc.do_thing(...)
```

### 7. Register in the container (`app/bootstrap/container.py`)

Add a module-level singleton and a getter:

```python
from app.services.<name> import MyModelAppService

_my_model_app_service: MyModelAppService | None = None

def get_my_model_app_service() -> MyModelAppService:
    global _my_model_app_service
    if _my_model_app_service is None:
        _my_model_app_service = MyModelAppService()
    return _my_model_app_service
```

### 8. Wire into the bot or API

**API route** (`app/api/routes/<name>.py`):

```python
from fastapi import APIRouter, Depends
from app.bootstrap.container import get_my_model_app_service

router = APIRouter()

@router.get("/my-models")
async def list_my_models(svc = Depends(get_my_model_app_service)):
    return await svc.list_all()
```

Then include the router in `app/main.py`:

```python
from app.api.routes.<name> import router as my_model_router
app.include_router(my_model_router)
```

**Bot handler** (`app/bot/handlers/<name>.py`):

```python
from aiogram import Router
from app.services.<name> import MyModelAppService

router = Router()

@router.message(...)
async def my_handler(message, my_model_app_service: MyModelAppService):
    await my_model_app_service.do_thing(...)
```

The `ServiceInjectionMiddleware` injects app services into handler kwargs by type name. Register the service there if not already present.

### 9. Register the model in Alembic (`alembic/env.py`)

```python
from app.modules.<name> import models as _<name>_models  # noqa: F401
```

### 10. Create and run the migration

```bash
python manage.py makemigration -m "add <name> table"
python manage.py migrate
```

---

## Architecture rules (enforced by tests)

The following are checked on every commit via pre-commit hooks:

| Rule | What it prevents |
|------|-----------------|
| No aiogram/FastAPI imports in `app/modules/` | Framework lock-in in domain logic |
| No DB access in handlers or routes | Skipping the service layer |
| Services created only via `container.py` | Hidden singletons and test-bypasses |
| `session_scope` only in `app/services/` | Transaction boundary ambiguity |
| Only `app/services/` commits | Repositories committing mid-transaction |

Violating any of these will fail `pre-commit` and CI.

---

## Running tests

```bash
python manage.py test           # full suite
python manage.py test -k users  # filter by name
```

## Linting and formatting

```bash
python manage.py lint    # ruff check
python manage.py format  # ruff format
python manage.py check   # lint + format + architecture tests
```
