# Building FastoGram (for contributors and coding agents)

The framework is built **spec-first**: every feature has a reviewed guide page in the separate
docs repo (`../docs/guide/T-xx-*.md`). The code must match the page. When the page and your idea
disagree, the page wins; if the page is wrong or impossible, say so in your report instead of
silently doing something else.

Spec precedence: `docs/plan/DECISIONS.md` > `docs/plan/LARAVEL-MAP.md` (names and import paths)
> the guide page > `docs/plan/RESEARCH-BASELINE.md`. Spike write-ups: `docs/research/spikes/`.

## Layout

```
src/fastogram/
  context.py          per-request context (ContextVar). Read its docstring first.
  config/             env(), config()
  foundation/         Application.configure()...create(), MiddlewareConfig, ExceptionsConfig,
                      stack.py (group stacks + exception boundaries), paths
  exceptions/         types.py = EVERY framework exception class; handler.py = report/render
  routing/ http/ session/ database/ inertia/ validation/ auth/ ...   one package per area
tests/
  test_spine_loop.py  end-to-end loop through the real stack; must always pass
  fixtures/blog/      a tiny app used by end-to-end tests
  <package>/          each package's own tests
spikes/               Phase 0 proof-of-concepts (reference code, not imported)
```

## How a request flows (read `foundation/stack.py`)

Global layers: `RequestContextMiddleware` → `MethodSpoofing` → `DatabaseScope` → user globals →
router. Each matched route's ASGI app is wrapped with its group's stack: for `web`,
`Boundary(StartSession(Boundary(AuthenticateSession(Boundary(PreventRequestForgery(Boundary(
HandleInertiaRequests(Boundary(endpoint))))))))`. Exceptions are rendered by the nearest
boundary through `fastogram.exceptions.handler`. Unknown URLs hit catch-all fallback routes
registered last, so they still pass through the group stack.

## Contracts between packages

- **Request context** (`fastogram.context`): `current()` / `require()`; fields `request`,
  `group`, `session`, `user`, `inertia`, `shared`, `route`, `route_params`, `extras`. The table in
  its docstring says which package writes which field. Only write your own fields.
- **Exceptions**: raise the classes in `fastogram.exceptions.types`; re-export them from your
  package at the LARAVEL-MAP §3 path. Never define a second class with the same meaning.
- **Session**: other packages use `fastogram.session.session()` and the `Session` methods named in
  T-18 only.
- **Database**: other packages use `Model`, `DB` and `fastogram.database.scope` only.
- **Framework middleware is pure ASGI** (D-025). Never use `BaseHTTPMiddleware`.
- **Lazy imports across packages** inside functions, to avoid import cycles at package import time.

## Rules for agents

1. Work **only inside the files and folders your task names**. If you need a change elsewhere
   (a shared file such as `context.py`, `foundation/*`, `exceptions/types.py`, or another
   package), do not make it: describe the exact change in your final report.
2. Do **not** commit, push, publish, or touch `../cli`, `../docs` or git state. The reviewer
   commits.
3. Public names and import paths come from LARAVEL-MAP. Do not invent public APIs; private
   helpers (`_name`) are fine.
4. Write tests in `tests/<package>/` with pytest (async tests need no decorator: asyncio auto
   mode). Test behaviour through the real stack where it matters (see `tests/test_spine_loop.py`
   and its fixture app), plus unit tests.
5. Before finishing run `uv run pytest -q` (everything, not just yours) and
   `uv run ruff check src tests`. Report the results honestly, including failures you could not fix.
6. Keep the code's style: type hints, short docstrings that say *why*, no print statements.
7. Spec gaps: choose the most Laravel-like behaviour, implement it, and list it in your report under
   "Decisions I made".

## Commands

```bash
uv sync                      # install
uv run pytest -q             # all tests
uv run ruff check src tests  # lint
DB_URL=postgresql+asyncpg://postgres:secret@127.0.0.1:55432/fastogram uv run pytest -q tests/database
```
