> **FastoGram is now [Aso](https://pypi.org/project/aso/).** This package is retired and gets no
> further updates. Start a new app with `uvx aso new myapp`; see https://github.com/Ibnu-Afdel/Aso.

# FastoGram

A Laravel-style web framework for Python: **FastAPI** on the backend, **Inertia.js v3 + React**
on the frontend, and an artisan-like CLI (`fastogram make:controller`, `fastogram migrate`, ...).

> **Status: early (0.1.1).** It works end to end, but expect rough edges and breaking changes.
> The previous Telegram bot template (0.0.x, FastAPI + aiogram) is kept under the tag
> `legacy-telegram-template` and on the `release/public-ready` branch.

## Try it

You need [uv](https://docs.astral.sh/uv/), Node 22+ and npm.

```bash
uvx fastogram new myapp     # like `laravel new myapp`
cd myapp
uv run fastogram dev        # server + Vite + route watcher
```

Open http://127.0.0.1:8000, register, and you're in the React starter kit (dashboard, settings,
password reset, email verification). In local mode mail goes to `storage/logs/`.

Useful commands: `fastogram list`, `fastogram route:list`, `fastogram make:model Post -mcr`,
`fastogram migrate`, `uv run pytest`.

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
src/fastogram/   the framework library and CLI (published to PyPI as `fastogram`)
skeleton/        the app that `fastogram new` creates (like laravel/laravel)
tests/           the framework's own tests
spikes/          Phase 0 proof-of-concept spikes (throwaway)
```

## License

MIT
