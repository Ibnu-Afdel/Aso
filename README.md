# Aso

The Aso framework is a Laravel-style web framework for Python: **FastAPI** on the backend,
**Inertia.js v3 + React** on the frontend, and an artisan-like CLI (`aso make:controller`,
`aso migrate`, ...).

> **Status: early (0.2.0).** It works end to end, but expect rough edges and breaking changes.
> The previous Telegram bot template (0.0.x, FastAPI + aiogram) is kept under the tag
> `legacy-telegram-template` and on the `release/public-ready` branch.

## Try it

You need [uv](https://docs.astral.sh/uv/), Node 22+ and npm.

```bash
uvx aso new myapp     # like `laravel new myapp`
cd myapp
uv run aso dev        # server + Vite + route watcher
```

Open http://127.0.0.1:8000, register, and you're in the React starter kit (dashboard, settings,
password reset, email verification). In local mode mail goes to `storage/logs/`.

Useful commands: `aso list`, `aso route:list`, `aso make:model Post -mcr`,
`aso migrate`, `uv run pytest`.

## What it looks like

```python
# routes/web.py
with Route.middleware("auth").group():
    Route.get("/posts", [PostController, "index"]).name("posts.index")
    Route.post("/posts", [PostController, "store"]).name("posts.store")

# app/http/controllers/post_controller.py
class PostController(Controller):
    async def index(self):
        return inertia("posts/index", {"posts": await Post.with_("author").latest().paginate(15)})

    async def store(self, form: StorePostRequest):
        await Post.create(**form.validated(), user_id=auth().id())
        return redirect().route("posts.index").with_flash("success", "Post created.")
```

## Repository layout

```
src/aso/   the framework library and CLI (published to PyPI as `aso`)
skeleton/        the app that `aso new` creates (like laravel/laravel)
tests/           the framework's own tests
spikes/          Phase 0 proof-of-concept spikes (throwaway)
```

## License

MIT
