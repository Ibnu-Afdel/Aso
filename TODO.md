# FastGram Starter-Kit TODO

## Immediate
- [x] Flatten project layout by removing `backend/` and moving code to root-level `app/`, `tests/`, `scripts/`, `alembic/`.
- [x] Replace `Makefile` workflows with `manage.py` and align tooling/docs paths (`Dockerfile`, Alembic, CLI help, README).
- [x] Regenerate lock file and validate clean install from scratch (`uv sync` and full `manage.py check` validation).

## Developer Experience
- [ ] Add full feature scaffolding command:
  - generate module (`models.py`, `schemas.py`, `repository.py`, `service.py`)
  - generate app-service boundary
  - generate bot handler + dispatcher registration stub
  - generate route stub (optional)
  - generate minimal tests
- [x] Add centralized command runner (`manage.py`) for setup/run/test/lint/format/check/shell/doctor/migrations/webhook/docker.
- [ ] Extend `manage.py doctor` with timeout support and richer diagnostics.
- [ ] Improve `manage.py make module/model` scaffolding to include app-service + route + handler + tests.
- [ ] Add `manage.py check` enhancements (optional strict import/layer checks output).
- [x] Add pre-commit hooks for Ruff + architecture guard tests.

## Documentation
- [ ] Before writing docs, manually verify:
  - `python manage.py check` passes on a clean shell.
  - `python manage.py run --reload` starts and `/health` returns `200`.
  - `python manage.py webhook --delete` and `python manage.py webhook` command paths run without import/runtime errors.
  - `python manage.py migrate` and `python manage.py makemigration -m "smoke_test"` command flows work (discard smoke revision after check).
  - `python manage.py docker-up` and `python manage.py docker-down` work with local Docker daemon.
  - Startup checks fail fast in production mode when required env is missing.
  - Request ID header (`X-Request-ID`) appears and changes per request.
  - Log output is readable in dev and structured JSON in production mode.

  
- [ ] Write "Fast Path" quickstart docs:
  - clone -> setup -> run -> add first `/start` feature -> test.
- [ ] Write architecture docs with one canonical flow:
  - handler/route -> app service -> module service -> repository.
- [ ] Write deployment docs:
  - polling mode
  - webhook mode behind reverse proxy
  - environment matrix (dev/stage/prod).
- [ ] Add troubleshooting docs:
  - DB connection failures
  - webhook 4xx/5xx
  - migration drift.

## Product Hardening
- [x] Add health/readiness checks split (`/healthz`, `/readyz`) with DB readiness probe.
- [ ] Add stronger startup checks for migration state in CI/CD pipeline.
- [ ] Add safe defaults for local onboarding (`BOT_ENABLED=false` quick mode).
- [ ] Add template branding cleanup and starter placeholders for new projects.

## Testing
- [ ] Expand architecture tests to enforce:
  - no framework imports in modules
  - no direct container usage in module layer
  - no direct DB engine usage outside infra.
- [ ] Add integration tests for:
  - webhook happy path
  - rollback path in app services
  - request-id propagation.

## Release Readiness
- [ ] Add GitHub Actions workflow (lint, tests, architecture guards).
- [ ] Add versioning/changelog policy.
- [ ] Add starter-kit release checklist and "template usage" guide.
