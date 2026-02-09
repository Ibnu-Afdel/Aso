# AI Contribution Rules

This file defines non-negotiable rules for AI-assisted changes in this repository.

## Architecture Rules
- **Modules** contain pure business logic (no FastAPI, no aiogram, no Telegram objects).
- **Bot handlers** call services.
- **API routes** call services.
- **Services** call repositories.
- **Repositories** talk to the database.
- **Async** everywhere.

## Layer Responsibilities
| Layer | Location | Responsibility |
| --- | --- | --- |
| Interface | bot/, api/ | Receive input |
| Application | modules/*/service.py | Business logic |
| Domain | modules/*/models.py | Data models |
| Infrastructure | modules/*/repository.py | DB access |
| Core | core/ | Config, DB, logging |

## Red Line Rules (Do Not Cross)
- Do **not** import aiogram inside modules.
- Do **not** put DB queries inside handlers.
- Do **not** put business logic inside routes.
- Do **not** call Telegram API from services.
- Do **not** mix layers.

## Always
- Handlers call services.
- Services call repositories.
- Modules stay pure.
- Keep async everywhere.

## Module Pattern
Every module must follow:
```
modules/<name>/
  models.py
  schemas.py
  repository.py
  service.py
```

## Bot Handler Pattern
- Create handler in `bot/handlers/<name>.py`.
- Handler must call service only.
- Register router in `bot/dispatcher.py`.

## API Route Pattern
- Routes act like controllers.
- Routes call services only.

## When Modifying Code
- Choose a single layer and apply changes there.
- If unsure, ask to clarify the layer to change.
