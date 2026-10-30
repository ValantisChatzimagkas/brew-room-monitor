# Backend rules (FastAPI)

## Layout
- `app/main.py` app + router registration · `app/config.py` settings · `app/db.py` engine/session
- `app/models.py` tables and API schemas · `app/deps.py` shared dependencies (session, auth) and `save_or_conflict` (commit, unique clash → 409)
- `app/routers/<resource>.py` one router per resource, mounted under `/api/v1`
- Add `app/services/<x>.py` only when logic is shared by 2+ routes or is non-trivial domain logic (e.g. yeast insights). Pure functions there, easy to unit test.

## FastAPI
- Endpoints are plain `def` (sync SQLModel session runs in the threadpool). Use `async def` only if everything awaited inside is async; never call blocking I/O inside `async def`.
- Declare the response type as the return annotation (`-> list[ReadingPublic]`). Never return a table model that holds secrets.
- Dependencies via `Annotated` aliases from `app/deps.py` (`SessionDep`, `DeviceDep`, `AdminDep`). Don't create sessions by hand in routes.
- Auth is explicit per router/route: admin routes use `AdminDep`, device ingest uses `DeviceDep`. A new router must pick one; there are no public data routes.
- Errors: raise `HTTPException` with the correct status (401 auth, 404 missing, 409 conflict, 422 invalid). Don't return error dicts with 200.
- Validate at the edge with Pydantic (`Field` bounds, `AwareDatetime`, `max_length` on lists/strings). Every list input has a max size.

## Security
- Every query param or body that can grow has an upper bound (`Field(max_length=...)`, `Query(le=...)`); every list endpoint has a `limit`.
- No `CORSMiddleware`: the browser never calls this API (the Next.js server does).
- SQL only through SQLModel/SQLAlchemy expressions. If raw SQL is unavoidable, `text()` with bound params, never f-strings.
- Never log request headers, tokens or token hashes. 401 responses stay generic (`_UNAUTHORIZED` in `app/deps.py`).
- Compare secrets with `secrets.compare_digest`; store device tokens hashed only (`app/security.py`).

## Data
- Schema convention: `XBase` shared fields → `X(table=True)` → `XCreate` / `XPublic`.
- Timestamps: `sa_column=tz_column()` + `utcnow()`. Ruff `DTZ` rules catch naive datetimes.
- Enums: `StrEnum` in Python, `sa_type=String(32)` in the DB.
- Every table change: `make migration m="..."`, review the file (autogenerate misses renames and data moves), `make migrate`. `alembic check` runs in CI.
- Time-series queries need an index that matches the filter.

## Quality bar
- `ruff format`, `ruff check` and `mypy --strict` clean. No `# type: ignore` / `# noqa` without a reason comment.
- No `print`; use `logging.getLogger(__name__)`.
- Config only via `get_settings()`; never read `os.environ` in app code.

## Tests (policy in root `CLAUDE.md`)
- Real Postgres (`brew_test` DB, created automatically; needs `make db`). Never SQLite, never a mocked session.
- Go through the HTTP API with the `client`, `admin_headers`, `device_headers` fixtures in `tests/conftest.py`. Add a fixture there only when a second test needs it.
- One file per router (`tests/test_<router>.py`). Plain unit tests only for pure functions in `app/services/` and startup validation in `app/config.py` (`tests/test_config.py`).
- See `test_rejects_bad_payloads` in `tests/test_readings.py` for the table style: many invalid inputs, one test.

## Deploy targets
Must keep working on both, so:
- Docker: `Dockerfile` runs `alembic upgrade head` then `exec`s `fastapi run`, so the app is PID 1 and receives SIGTERM.
- FastAPI Cloud: `fastapi deploy` from `backend/` uses `[tool.fastapi] entrypoint` in `pyproject.toml`. Point `DATABASE_URL` at a managed Postgres, set `ADMIN_TOKEN` + `ENVIRONMENT=production`, run migrations as a separate step against that DB.
- So: stateless app, no writes to local disk, no background threads that must survive restarts, everything configured by env.
