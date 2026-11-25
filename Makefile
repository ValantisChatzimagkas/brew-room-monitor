# `dev` needs `wait -n` (bash >= 4.3; macOS ships 3.2, install a newer bash) and job control; /bin/sh may be dash.
SHELL := bash

.PHONY: help setup db dev dev-backend dev-frontend api-types check-api-types migration migrate check check-backend check-frontend audit auth-env up down logs db-reset smoke

# Root .env is the only env file: its values reach every recipe (dev-*, check-*, up, smoke).
# Inside make the file wins over a same-named shell variable; write values unquoted (Makefile syntax).
ifneq (,$(wildcard .env))
include .env
export
endif

.DEFAULT_GOAL := help

# Reads the Makefile only: $(MAKEFILE_LIST) also holds the included .env.
help:          ## list targets
	@grep -E '^[a-zA-Z_-]+:.*## ' $(firstword $(MAKEFILE_LIST)) | awk -F':.*## ' '{printf "%-16s %s\n", $$1, $$2}'

setup:         ## create .env from .env.example (skips an existing file)
	@if [ -e .env ]; then echo ".env exists, skipped"; \
	else cp .env.example .env && echo "created .env"; fi

db:            ## start Postgres only, wait until it accepts connections
	docker compose up -d --wait db

# One process group per server (set -m), so the kill also reaches the reloader's worker and next-server.
# Under set -m a terminal Ctrl-C or hangup reaches only make's own group, hence the traps. No set -e:
# a failing `wait -n` must not skip killing the survivor. Postgres stays up: `make down` stops it.
dev: auth-env db  ## Postgres + API + frontend with reload; Ctrl-C stops both servers
	@set -m; \
	stop() { trap '' INT TERM HUP; kill -TERM -$$api -$$web 2>/dev/null; wait; exit $$1; }; \
	trap 'stop 130' INT; trap 'stop 143' TERM; trap 'stop 129' HUP; \
	$(MAKE) dev-backend & api=$$!; \
	$(MAKE) dev-frontend & web=$$!; \
	wait -n; stop $$?

dev-backend:   ## API with reload on :8000
	cd backend && uv run alembic upgrade head && uv run fastapi dev

dev-frontend: auth-env  ## Next.js on :3000
	cd frontend && pnpm dev

# Sign-in has no dev bypass and can't work with any of these unset (the dashboard 500s or the backend
# won't boot), so refuse to start.
# APP_BASE_URL is left out: the SDK falls back to the request's host.
AUTH_ENV := AUTH_ISSUER AUTH_AUDIENCE AUTH0_DOMAIN AUTH0_CLIENT_ID AUTH0_CLIENT_SECRET AUTH0_SECRET
auth-env:
	@missing="$(strip $(foreach v,$(AUTH_ENV),$(if $($(v)),,$(v))))"; \
	[ -z "$$missing" ] || { echo "Missing in .env: $$missing. The dashboard needs an Auth0 tenant: see README.md, Quick start." >&2; exit 1; }

OPENAPI ?= frontend/openapi.json
SCHEMA ?= frontend/src/lib/api/schema.d.ts

api-types:     ## regenerate frontend types from the backend OpenAPI schema
	cd backend && uv run python -c "import json; from app.main import app; print(json.dumps(app.openapi(), indent=2))" > $(abspath $(OPENAPI))
	cd frontend && pnpm exec openapi-typescript $(abspath $(OPENAPI)) -o $(abspath $(SCHEMA))

# Generates into a temp dir, so it passes with regenerated-but-unstaged files (unlike `git diff`).
check-api-types:  ## fail if the frontend API types are stale
	@tmp=$$(mktemp -d) && $(MAKE) -s api-types OPENAPI=$$tmp/openapi.json SCHEMA=$$tmp/schema.d.ts >/dev/null \
	  && diff -q $$tmp/openapi.json $(OPENAPI) && diff -q $$tmp/schema.d.ts $(SCHEMA) \
	  || { echo "Frontend API types are stale: run 'make api-types'"; exit 1; }

migration:     ## make migration m="describe change"
	cd backend && uv run alembic revision --autogenerate -m "$(m)"

migrate:       ## apply database migrations
	cd backend && uv run alembic upgrade head

check: check-backend check-frontend  ## everything the `backend` and `frontend` CI jobs run (CI calls these targets)

check-backend: ## ruff, mypy, migrations and pytest (the `backend` CI job)
	cd backend && uv run ruff format --check . && uv run ruff check . && uv run mypy . && uv run alembic upgrade head && uv run alembic check && uv run pytest

check-frontend: check-api-types  ## lint, typecheck, test, build and API-types check (the `frontend` CI job)
	cd frontend && pnpm lint && pnpm typecheck && pnpm test && pnpm build

audit:         ## known CVEs in runtime deps (own CI workflow, not part of `check`)
	cd backend && uv export --locked --no-dev --no-emit-project -q | uvx pip-audit@2.10.1 -r /dev/stdin --disable-pip --strict
	cd frontend && pnpm audit --prod --audit-level=high

up: auth-env   ## full stack in Docker
	docker compose up --build

down:          ## stop the compose stack (keeps the database volume)
	docker compose down

logs:          ## tail the compose stack's logs
	docker compose logs -f --tail=100

# No -p: like db and up this acts on the default compose project, never on smoke's brew-smoke.
db-reset:      ## wipe the dev database volume (asks first)
	@printf "Deletes the dev database volume (pgdata) and stops the compose stack. Type 'yes' to continue: "; \
	read answer; [ "$$answer" = yes ] || { echo aborted; exit 1; }; \
	docker compose down -v

# Own compose project, so a run never touches the dev stack's volume. Host ports are shared with
# the dev stack: stop it first (a clash fails fast with "port is already allocated").
# Dummy Auth0 values: nothing here talks to a tenant. AUTH_ISSUER is set too because the backend refuses
# to boot with only one of AUTH_ISSUER / AUTH_AUDIENCE. No signed-in path is covered (no fake issuer in
# compose); the frontend's own checks are the redirect for anonymous visitors and a reachable backend.
smoke:         ## build the images, boot the compose stack, assert it works end to end (needs ports 3000/8000/5432 free)
	@set -e; \
	export COMPOSE_PROJECT_NAME=brew-smoke \
	  AUTH0_DOMAIN=smoke.invalid AUTH0_CLIENT_ID=smoke AUTH0_CLIENT_SECRET=smoke \
	  AUTH0_SECRET=$$(python3 -c "import secrets; print(secrets.token_hex(32))") APP_BASE_URL=http://localhost:3000 \
	  AUTH_AUDIENCE=https://smoke.invalid/api AUTH_ISSUER=https://smoke.invalid/; \
	trap 'rc=$$?; set +e; if [ $$rc -ne 0 ]; then docker compose ps -a; docker compose logs; fi; docker compose down -v --remove-orphans; exit $$rc' EXIT; \
	trap 'exit 130' INT; trap 'exit 143' TERM; \
	docker compose up --build --wait; \
	curl -fsS http://localhost:8000/health >/dev/null; \
	anon=$$(curl -sS -o /dev/null -w '%{http_code} %{redirect_url}' http://localhost:3000/); \
	case "$$anon" in "307 "*/auth/login*) ;; *) echo "smoke: anonymous GET / should redirect to sign-in, got: $$anon"; exit 1;; esac; \
	docker compose exec -T frontend sh -c 'wget -q -O /dev/null "$$API_URL/health"'; \
	echo "smoke: ok"
