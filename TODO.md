# FastGram Starter-Kit TODO

## Immediate
- [x] Flatten project layout by removing `backend/` and moving code to root-level `app/`, `tests/`, `scripts/`, `alembic/`.
- [ ] Verify all tooling/docs paths after flattening (`Makefile`, `Dockerfile`, Alembic, CLI help, README).
- [ ] Regenerate lock file and validate clean install from scratch (`uv sync` on fresh clone).

## Developer Experience
- [ ] Add full feature scaffolding command:
  - generate module (`models.py`, `schemas.py`, `repository.py`, `service.py`)
  - generate app-service boundary
  - generate bot handler + dispatcher registration stub
  - generate route stub (optional)
  - generate minimal tests
- [ ] Add `make check` target to run lint + tests + architecture guards in one command.
- [ ] Add `make test` target and CI-ready test command.
- [ ] Add pre-commit hooks for Ruff + architecture guard tests.

## Documentation
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
- [ ] Add health/readiness checks split (`/healthz`, `/readyz`) with DB readiness probe.
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
