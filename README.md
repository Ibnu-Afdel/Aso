# FastoGram

A Laravel-style web framework for Python: **FastAPI** on the backend, **Inertia.js v3 + React**
on the frontend, and an artisan-like CLI (`fastogram make:controller`, `fastogram migrate`, ...).

> **Status: under construction (v0.1.0.dev).** The rewrite is in progress on `main`. The previous
> Telegram bot template (FastAPI + aiogram) is kept under the tag `legacy-telegram-template` and
> on the `release/public-ready` branch.

## What it will look like

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
