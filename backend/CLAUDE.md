# Backend rules (FastAPI)

## Layout
- `app/main.py` app + router registration · `app/config.py` settings · `app/db.py` engine/session · `app/oidc.py` user-JWT verification (fetches the issuer's keys)
- `app/models.py` tables and API schemas · `app/deps.py` shared dependencies (session, auth), `save_or_conflict` (commit, unique clash → 409) and `get_batch_or_404`
- `app/routers/<resource>.py` one router per resource, mounted under `/api/v1`
- `app/seed.py` local demo data through the HTTP API (`make seed`)
- Add `app/services/<x>.py` only when logic is shared by 2+ routes or is non-trivial domain logic (e.g. yeast insights). Pure functions there, easy to unit test.

## FastAPI
- Endpoints are plain `def` (sync SQLModel session runs in the threadpool). Use `async def` only if everything awaited inside is async; never call blocking I/O inside `async def`.
- Declare the response type as the return annotation (`-> list[ReadingPublic]`). Never return a table model that holds secrets.
- Dependencies via `Annotated` aliases from `app/deps.py` (`SessionDep`, `DeviceDep`, `UserDep`). Don't create sessions by hand in routes.
- Auth is explicit per router/route: device ingest uses `DeviceDep`, user routes use `UserDep`. A new router must pick one; there are no public data routes. A route that returns or changes an owner's rows takes `UserDep` and filters with `owned`; a foreign row is a 404/422, never a 403. To get a user token for `curl`, see `firmware/README.md` ("Getting a user token").
- Errors: raise `HTTPException` with the correct status (401 auth, 404 missing, 409 conflict, 422 invalid). Don't return error dicts with 200.
- Validate at the edge with Pydantic (`Field` bounds, `AwareDatetime`, `max_length` on lists/strings). Every list input has a max size.

## Security
- Every query param or body that can grow has an upper bound (`Field(max_length=...)`, `Query(le=...)`); every list endpoint bounds its rows: a `limit`, or a cap it rejects with 422 when cutting rows would mislead.
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
- Real Postgres (`brew_test` DB, created automatically; needs `make db`). Never SQLite, never a mocked session. `_database` in `tests/conftest.py` builds its schema with `alembic upgrade head` once per session (tables are emptied between tests), so a migration is tested the way production runs it.
- Any warning fails the run. Ignore one on purpose only via `filterwarnings` in `pyproject.toml`, with a reason comment beside it.
- Go through the HTTP API with the `client`, `user_headers`, `device_headers` fixtures in `tests/conftest.py`. Add a fixture there only when a second test needs it.
- One file per router (`tests/test_<router>.py`), plus `tests/test_auth.py`, `tests/test_migrations.py` (a data migration, run against the real test DB) and `tests/test_seed.py` (drives `app/seed.py` through `client`) as the cross-cutting exceptions. Plain unit tests only for pure functions in `app/services/` and startup validation in `app/config.py` (`tests/test_config.py`).
- `tests/test_auth.py` walks every registered route (missing, unknown and wrong-kind token → 401), so don't write per-route auth tests. A new device-token route goes in `DEVICE_ROUTES`, a new user-JWT route in `USER_ROUTES`, a new public route in `EXEMPT_PATHS` (needs a reason); a route in no table must reject every token kind.
- User-JWT tests sign tokens with the local fake issuer fixture (`issuer`, `make_user_token`) in `tests/conftest.py`; never mock `app/oidc.py` (patching its `JWKS_*` tuning constants is fine).
- See `test_rejects_bad_payloads` in `tests/test_readings.py` for the table style: many invalid inputs, one test.

## Deploy targets
Must keep working on both, so:
- Docker: `Dockerfile` runs `alembic upgrade head` then `exec`s `fastapi run`, so the app is PID 1 and receives SIGTERM.
- FastAPI Cloud: `fastapi deploy` from `backend/` uses `[tool.fastapi] entrypoint` in `pyproject.toml`. Point `DATABASE_URL` at a managed Postgres that allows the `btree_gist` extension (the batch migration creates it), set `AUTH_ISSUER` + `AUTH_AUDIENCE` + `ENVIRONMENT=production` (the app needs outbound HTTPS to the issuer for its signing keys), run migrations as a separate step against that DB.
- So: stateless app, no writes to local disk, no background threads that must survive restarts, everything configured by env.
