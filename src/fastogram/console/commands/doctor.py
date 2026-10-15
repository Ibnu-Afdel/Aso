"""`fastogram doctor` and `agents:update` (T-61).

`doctor` runs a handful of cheap, mostly-static checks and prints `[PASS]`/`[WARN]`/`[FAIL]`
lines, exiting non-zero if anything failed. `agents:update` (re)writes the framework's section of
`AGENTS.md`, the rules file AI coding agents are told to read first (T-61 "Rules for AI agents"),
between `<!-- fastogram:start -->`/`<!-- fastogram:end -->` markers so an app's own notes appended
below them survive an upgrade (T-61 "Open questions" #2 names this exact marker scheme).
"""

from __future__ import annotations

import re
from typing import Any

from fastogram.console.command import Command
from fastogram.console.commands.make import render_stub
from fastogram.console.registry import register

_START = "<!-- fastogram:start -->"
_END = "<!-- fastogram:end -->"


# ---------------------------------------------------------------- doctor


def _paths() -> Any:
    from fastogram.foundation import paths

    return paths


async def _check_database_and_migrations() -> list[tuple[str, str]]:
    try:
        from fastogram.database.engine import engine

        async with engine().connect() as conn:
            await conn.run_sync(lambda _conn: None)
    except Exception as exc:  # noqa: BLE001 - reported to the user, not re-raised
        return [("FAIL", f"Database connection: could not connect ({exc})")]

    results = [("PASS", "Database connection: connected")]
    try:
        from fastogram.console import migrations

        rows = await migrations.status()
        pending = [r for r in rows if not r.applied]
        if pending:
            results.append(("FAIL", f"Migrations: {len(pending)} pending (run `fastogram migrate`)"))
        else:
            results.append(("PASS", f"Migrations: up to date ({len(rows)} applied)"))
    except Exception as exc:  # noqa: BLE001
        results.append(("FAIL", f"Migrations: could not check status ({exc})"))
    return results


def _missing_inertia_pages() -> list[str]:
    """A cheap, regex-based scan (not AST) for `inertia("some/page")` literals in
    `app/http/controllers/`, checked against `resources/js/pages/<page>.tsx` (T-58's A4
    architecture rule does the real, AST-based version of this at test time)."""
    controllers_dir = _paths().app_path("http", "controllers")
    if not controllers_dir.is_dir():
        return []
    pattern = re.compile(r"""inertia\(\s*["']([\w\-/]+)["']""")
    missing: list[str] = []
    for path in controllers_dir.rglob("*.py"):
        for match in pattern.finditer(path.read_text()):
            page = match.group(1)
            if page not in missing and not _paths().resource_path("js", "pages", f"{page}.tsx").is_file():
                missing.append(page)
    return missing


async def run_checks() -> list[tuple[str, str]]:
    import shutil
    import subprocess
    import sys

    paths = _paths()
    results: list[tuple[str, str]] = []

    results.append(("PASS", f"Python version: {'.'.join(str(p) for p in sys.version_info[:3])}"))

    if paths.base_path(".env").is_file():
        results.append(("PASS", ".env file: present"))
    else:
        results.append(("WARN", ".env file: missing (copy .env.example to .env)"))

    from fastogram.config import config

    if config("app.key"):
        results.append(("PASS", "Application key: configured"))
    else:
        results.append(("FAIL", "Application key: not set (run `fastogram key:generate`)"))

    results.extend(await _check_database_and_migrations())

    manifest = paths.public_path("build", "manifest.json")
    hot = paths.public_path("hot")
    if manifest.is_file():
        results.append(("PASS", "Frontend assets: manifest verified (public/build/manifest.json)"))
    elif hot.is_file():
        results.append(("PASS", "Frontend assets: Vite dev server running (public/hot)"))
    else:
        results.append(("WARN", "Frontend assets: no build manifest and no Vite dev server (run `npm run build` or `npm run dev`)"))

    if paths.base_path("node_modules").is_dir():
        results.append(("PASS", "Node dependencies: node_modules present"))
    else:
        results.append(("WARN", "Node dependencies: node_modules missing (run `npm install`)"))

    node = shutil.which("node")
    if node:
        try:
            version = subprocess.run([node, "--version"], capture_output=True, text=True, timeout=5, check=False).stdout.strip()
            results.append(("PASS", f"Node version: {version or 'unknown'}"))
        except OSError:
            results.append(("WARN", "Node version: could not run `node --version`"))
    else:
        results.append(("WARN", "Node version: node not found on PATH"))

    missing_pages = _missing_inertia_pages()
    if missing_pages:
        results.append(("FAIL", f"Inertia pages: missing {', '.join(sorted(missing_pages))}"))
    else:
        results.append(("PASS", "Inertia pages: every statically-found inertia(...) call has a matching page"))

    return results


class DoctorCommand(Command):
    signature = "doctor"
    description = "Check the application's environment for common problems"

    async def handle(self) -> int:
        self.line("FastoGram Diagnostic Doctor")
        self.new_line()
        results = await run_checks()
        failed = False
        for status, message in results:
            if status == "FAIL":
                failed = True
                self.error(f"[FAIL] {message}")
            elif status == "WARN":
                self.warn(f"[WARN] {message}")
            else:
                self.info(f"[PASS] {message}")
        self.new_line()
        if failed:
            self.error("Some checks failed.")
            return 1
        self.info("Everything looks healthy!")
        return 0


# ---------------------------------------------------------------- agents:update


_AGENTS_BODY = """# Instructions for AI Agents

You are developing on a FastoGram project (FastAPI + Inertia.js v3 + React 19).
Follow these conventions strictly.

## 1. Generator First
Always generate code using `fastogram make:*` commands rather than writing empty files manually:
- `fastogram make:model Post -a --fields="title:string body:text"`
- `fastogram make:controller PostController --resource --model=Post --requests`
- `fastogram make:request StorePostRequest`
- `fastogram make:page posts/index`
- `fastogram make:test PostTest`

## 2. Architecture Rules (A1-A13)
The project runs AST-based architecture tests in `tests/architecture/`. Never violate these rules:
- A1: Controllers must not import `sqlalchemy`. Move queries to model scopes or methods.
- A2: Models must not import `fastapi`, `starlette`, or `fastogram.http`. Models must function without HTTP requests.
- A3: Controller methods must not read raw request input (`request.input()`, `request.json()`). Take a `FormRequest` parameter instead.
- A4: Pages passed to `inertia("posts/index")` must exist in `resources/js/pages/posts/index.tsx`.
- A5: Do not import a third-party Inertia adapter (`cross_inertia`, `inertia`, `fastapi_inertia`). Use `fastogram.inertia`.
- A6: Never interpolate raw SQL with f-strings, `%`, or `+`. Use parameterized `:name` bindings.
- A7: Do not use `print()` or `breakpoint()`. Use `from fastogram.log import log`.
- A8: Do not subclass `BaseHTTPMiddleware`. Inherit from `fastogram.http.Middleware`.
- A9: Do not create manual SQLAlchemy engines or sessions. Use `from fastogram.database import DB`.
- A10: Form request classes in `app/http/requests/` must extend `FormRequest` and end with `Request`.
- A11: Every model in `app/models/` must define `__fillable__` or `__guarded__`.
- A12: Background jobs in `app/jobs/` must accept scalar IDs in constructors, never model instances.
- A13: Do not read `os.environ` outside `config/`. Use `from fastogram.config import config`.

## 3. Inertia v3 Conventions
- Page names are lowercase paths: `inertia("posts/index")`.
- No Axios. Use Inertia's `<Form>`, `useForm`, `router`, or `useHttp`.
- On validation failure, web controllers redirect back; they never return 422 JSON.
- Never hard-code URLs in TSX. Import route helpers from `@/routes/...` (run `fastogram routes:generate`).
- Pages never wrap themselves in `<AppLayout>`; pass breadcrumbs with `Page.layout = { breadcrumbs }`.
- Flash messages arrive in `usePage().flash`. Never add `flash` to `share()`.

## 4. Backend habits
- Every write action (store, update, destroy) ends with `redirect(...).with_flash("success", ...)`.
- Call `await self.authorize(...)` before changing a model the user might not own.
- Eager load relations with `with_("author")` or `await post.load("author")`. Unloaded relations raise `LazyLoadingViolation`.
- Everything that touches the database is `async`: `await Post.find(1)`, `await post.save()`.
- Group multi-step writes in `async with DB.transaction():`.
- Paginate lists (`.paginate(15)`); never `get()` an unbounded table for a page.
- Jobs take ids, never models; reload in `handle()`.

## 5. Before you finish
- `fastogram test` passes, including `tests/architecture/`.
- New routes have a feature test: happy path, validation failure, authorization failure."""


class AgentsUpdateCommand(Command):
    signature = "agents:update {--force : Overwrite even if the markers are missing}"
    description = "(Re)write the AGENTS.md rules section for AI coding agents"

    async def handle(self) -> int:
        path = _paths().base_path("AGENTS.md")
        rendered = render_stub("agents_md.stub", {"content": _AGENTS_BODY}).rstrip("\n")
        block = f"{_START}\n{rendered}\n{_END}"

        if not path.is_file():
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(block + "\n")
            self.info("Created AGENTS.md.")
            return 0

        existing = path.read_text()
        if _START in existing and _END in existing:
            start = existing.index(_START)
            end = existing.index(_END) + len(_END)
            path.write_text(existing[:start] + block + existing[end:])
            self.info("Updated the FastoGram section of AGENTS.md.")
            return 0

        if self.option("force"):
            path.write_text(block + "\n")
            self.info("Overwrote AGENTS.md (no markers were found).")
            return 0

        self.error("AGENTS.md exists but has no <!-- fastogram:start/end --> markers. Pass --force to overwrite it.")
        return 1


def register_all() -> None:
    for cls in (DoctorCommand, AgentsUpdateCommand):
        register(cls, source="framework")
