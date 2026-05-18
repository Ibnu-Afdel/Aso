# Vibecoder Guide

You use AI to write code. You don't need to understand every line. This guide tells you **what to ask** and **what to expect**.

## How It Works

1. **You describe** what you want in plain English.
2. **AI asks** 1–2 clarifying questions if needed.
3. **You answer.** AI writes code in the right places.
4. **Done.** Run `python manage.py run` and test.

## Quick Start (First Time)

```bash
cp .env.example .env
# Edit .env: set TELEGRAM_BOT_TOKEN (get from @BotFather)
python manage.py demo
```

That's it. The bot + API are running.

## What to Ask AI

### Add a new feature (e.g. "save notes")

> "Add a notes feature: users can save one note via /note <text> and read it with /mynote."

AI will:
- Create a `notes` module (models, repo, service)
- Add an app service
- Add bot handlers
- Wire everything

**You do:** Run `python manage.py migrate` if it tells you to. Test the bot.

### Add a new command

> "Add a /stats command that shows how many notes the user has."

AI will add a handler that calls the notes service. You do nothing else.

### Add an API endpoint

> "Add an API route GET /api/notes that returns the current user's note."

AI will add a route. You might need to set `X-Telegram-Init-Data` when calling from a WebApp.

### Fix something

> "The /mynote command returns empty. Fix it."

Describe the symptom. AI will find and fix.

## What AI Won't Do (On Purpose)

- Put database code inside handlers
- Put business logic inside routes
- Mix Telegram code with modules

The template has strict rules. AI is instructed to follow them. If you see "red line" or "architecture" in an error, that means something was put in the wrong place. Ask AI to fix it.

## Useful Commands

| Command | When to use |
| --- | --- |
| `python manage.py demo` | First run. Setup + migrate + start. |
| `python manage.py run` | Start the app (after setup). |
| `python manage.py make module X` | Scaffold a new module (AI usually does this for you). |
| `python manage.py migrate` | Apply DB changes. |
| `python manage.py --help` | See all commands. |

## If Something Breaks

1. **Import error** — Run `python manage.py setup` (installs deps).
2. **DB error** — Run `python manage.py migrate`. If first time, ensure Postgres is running (e.g. `docker compose up -d db`).
3. **Bot not responding** — Check `TELEGRAM_BOT_TOKEN` in `.env`.
4. **Architecture test failed** — Ask AI: "Fix the architecture violation: [paste error]."

## Summary

**You:** Describe features in plain English.  
**AI:** Writes code in the right layers.  
**Template:** Enforces structure so nothing breaks.

Focus on *what* you want. AI handles *where* and *how*.
