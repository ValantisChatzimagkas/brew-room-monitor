# Brew Room Monitor

Sensors (ESP32 now, in-fermenter capsules later) push readings → FastAPI stores them in Postgres → Next.js shows brewing-room conditions and, later, yeast insights (is the room/wort inside the yeast's range, how fermentation is progressing).

## Layout
- `backend/` FastAPI + SQLModel + Alembic, managed with `uv`. Rules: `backend/CLAUDE.md`
- `frontend/` Next.js (App Router) + Tailwind, managed with `pnpm`. Rules: `frontend/CLAUDE.md`
- `firmware/` device ↔ API contract for sensor code
- `docker-compose.yml` local stack (db, backend, frontend)
- How the parts connect and why: `ARCHITECTURE.md`. Read it before adding a component or changing a boundary.

## Commands (from repo root)
- `make help` → every target with its description
- `make dev` → Postgres + backend + frontend with hot reload (Ctrl-C stops the servers); single pieces: `make db`, `make dev-backend`, `make dev-frontend`
- `make down` / `make logs` / `make db-reset` → stop the compose stack / tail its logs / wipe the dev database (`db-reset` prompts)
- `make check` → everything CI runs except `make audit` (dependency CVEs, separate workflow) and `make smoke` (Docker stack boot, own CI job). **Must pass before you call a task done.**
- One backend test: `cd backend && uv run pytest tests/test_readings.py -k ingest` (needs `make db`)
- `make api-types` → regenerate frontend types after any backend schema/route change
- `make migration m="..."` → after any table change; read the generated file before committing

## Guardrails (apply everywhere)
- **Backend owns the contract.** Frontend types are generated from OpenAPI, never hand-written. CI fails if `frontend/openapi.json` is stale.
- **Time:** store and transmit timezone-aware UTC only. Convert to local time in the UI, nowhere else.
- **Units live in the name** (`temperature_c`, `humidity_pct`). Never store a bare `temperature`.
- **Secrets:** env vars only, never committed, never in `NEXT_PUBLIC_*`, never logged or echoed in responses/errors. The admin token stays on servers; devices get their own per-device token.
- **The frontend has no user login yet.** Anyone who can reach it sees what it renders, and every Server Action is a public POST endpoint. So: no mutating Server Actions and no public deployment of the frontend until auth exists.
- **Device API is versioned** (`/api/v1`). Flashed devices can't be updated easily: never make a breaking change to `POST /api/v1/readings`; add `/v2` instead.
- **Schema changes go through Alembic.** No `create_all` outside tests. No Postgres native enums (use strings + Python `StrEnum`).

## Before writing code: extend, don't add
- **Search first.** Before adding a function, schema, dependency, component, route or test fixture, `grep` for one that already does something close. Extend it instead of adding a parallel one. In your summary, name what you reused or why nothing fit.
- **Read the neighbours.** Open the file you're changing, one caller and one sibling (another router, another component) and copy their pattern. If the repo has a pattern, follow it; don't add a second way.
- **Smallest diff that solves the task.** No drive-by refactors, renames or reformatting. No speculative abstractions, config flags or "for later" code.
- Extract a helper/module on the second real use, not the first. Delete dead code; don't comment it out. Comments explain *why*, not *what*.
- **New dependency, new layer or new top-level folder: propose it first** and say what code or risk it removes. Then say why in the commit.

## Tests: few, and each one earns its place
- Test behaviour through the boundary someone actually uses (HTTP API, device contract, rendered page), not internals. A refactor that keeps behaviour must not break a test.
- Must test: input bounds on anything a device sends, every status code in `firmware/README.md`, domain logic (insights) including edge cases.
- Auth is tested once for every route by `backend/tests/test_auth.py`; a new route needs no auth test of its own.
- Don't test: framework or library behaviour, things the type checker already proves, private helpers, trivial pass-throughs. No mocks of our own code or of the DB. No snapshot tests.
- One test per behaviour. Variants of the same rule go in a table (a list or `pytest.mark.parametrize`), not copy-pasted tests. Add to the existing test file and fixtures before creating new ones.
- Behaviour change ⇒ test change. Bug fix ⇒ failing regression test first, then the fix.

## Docs: one home per fact, fixed in the same commit
- **Where things live.** `README.md`: what this is and how to run it. `ARCHITECTURE.md`: how the parts connect, the boundaries and the reasons behind them. `CLAUDE.md` files: rules for changing code (humans and agents), in the most local one that applies. `firmware/README.md`: the device contract. API reference: generated OpenAPI (`/docs`), never hand-written. Infra (`docker-compose.yml`, Dockerfiles, CI): the files are the docs; comment only the non-obvious why. The reason for a change goes in the commit body.
- **Link, don't copy.** Commands live in the `Makefile`, env vars in `.env.example`, API shapes in OpenAPI. Docs name the target or file; they don't repeat its contents or list its fields.
- **Same commit.** A change that makes a doc wrong fixes that doc in the same commit: `make` target or env var → `README.md` / `.env.example`; device endpoint, payload bound or status code → `firmware/README.md`; new component, boundary, cross-folder flow or data-model principle → `ARCHITECTURE.md`; new pattern, or a path/symbol a `CLAUDE.md` names → that `CLAUDE.md`.
- **Rules earn their line.** If lint, types, a test or a hook can enforce it, do that instead. Write a rule as a specific instruction; add the why only when it isn't obvious. Changing a rule means editing or deleting the old one, never adding a second that disagrees. Keep each `CLAUDE.md` under ~100 lines: cut stale rules before adding or splitting.
- **No speculative docs.** No docs site, changelog, diagram files or per-folder READMEs until someone needs one. Write a decision record (`docs/decisions/NNNN-title.md`: context, decision, consequences, a few lines) only for a hard-to-reverse choice whose reasoning doesn't fit in a line of `ARCHITECTURE.md`; propose the folder the first time.

## Agent setup (`.claude/`)
- `settings.json` enforces: `.env*` files unreadable, generated files and lockfiles not hand-editable (use `make api-types`, `uv add`, `pnpm add`), `shadcn add` limited to the official registry, Python auto-formatted on save, lint + types re-checked when you stop, and a hook (`hooks/block-dangerous-git.sh`) that blocks pushes to `main`, force-push, `reset --hard`, `clean -f`, `branch -D` and `checkout .` / `restore .`. `main` has no GitHub-side protection (private repo, free plan), so that hook is the only guard: all changes reach `main` through a PR.
- After a non-trivial change, run the `reviewer` agent on the diff and fix what it finds before calling the task done.
- Issues live in Linear; create and edit them only through the `linear-issue` skill (template, labels, target project).
- Open and edit PRs only through the `pull-request` skill (template in `.github/pull_request_template.md`).
- `skills/shadcn` is copied from `shadcn/ui` (via `skills add`) and patched to use the pinned CLI and the official registry only. If you update it, re-apply those edits.

## Domain glossary
- **Device**: one sensor node. `ambient` (room) or `in_vessel` (floats in the fermenter).
- **Reading**: one `(device, metric, value, recorded_at)` sample.
- **Batch** / **Yeast profile** (not built yet): a brew with a yeast strain and its temperature range; insights compare readings against it.

## Commits
Conventional Commits (`feat:`, `fix:`, `refactor:`, `chore:`…), small and focused. Don't commit `.env*` files.
