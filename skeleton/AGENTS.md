# Instructions for AI Agents

You are developing on an Aso project (FastAPI + Inertia.js v3 + React 19).
Follow these conventions strictly.

## 1. Generator First
Always generate code using `aso make:*` commands rather than writing empty files manually:
- `aso make:model Post -a --fields="title:string body:text"`
- `aso make:controller PostController --resource --model=Post --requests`
- `aso make:request StorePostRequest`
- `aso make:page posts/index`
- `aso make:test PostTest`

## 2. Architecture Rules (A1-A13)
The project runs AST-based architecture tests in `tests/architecture/`. Never violate these rules:
- A1: Controllers must not import `sqlalchemy`. Move queries to model scopes or methods.
- A2: Models must not import `fastapi`, `starlette`, or `aso.http`. Models must function without HTTP requests.
- A3: Controller methods must not read raw request input (`request.input()`, `request.json()`). Take a `FormRequest` parameter instead.
- A4: Pages passed to `inertia("posts/index")` must exist in `resources/js/pages/posts/index.tsx`.
- A5: Do not import a third-party Inertia adapter (`cross_inertia`, `inertia`, `fastapi_inertia`). Use `aso.inertia`.
- A6: Never interpolate raw SQL with f-strings, `%`, or `+`. Use parameterized `:name` bindings.
- A7: Do not use `print()` or `breakpoint()`. Use `from aso.log import log`.
- A8: Do not subclass `BaseHTTPMiddleware`. Inherit from `aso.http.Middleware`.
- A9: Do not create manual SQLAlchemy engines or sessions. Use `from aso.database import DB`.
- A10: Form request classes in `app/http/requests/` must extend `FormRequest` and end with `Request`.
- A11: Every model in `app/models/` must define `__fillable__` or `__guarded__`.
- A12: Background jobs in `app/jobs/` must accept scalar IDs in constructors, never model instances.
- A13: Do not read `os.environ` outside `config/`. Use `from aso.config import config`.

## 3. Inertia v3 Conventions
- Page names are lowercase paths: `inertia("posts/index")`.
- No Axios. Use Inertia's `<Form>`, `useForm`, `router`, or `useHttp`.
- On validation failure, web controllers redirect back; they never return 422 JSON.
- Never hard-code URLs in TSX. Import route helpers from `@/routes/...` (run `aso routes:generate`).
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
- `aso test` passes, including `tests/architecture/`.
- New routes have a feature test: happy path, validation failure, authorization failure.
