.PHONY: setup db dev-backend dev-frontend api-types check-api-types migration migrate check check-backend check-frontend audit up smoke

# Root .env is the only env file: its values reach every recipe (dev-*, check-*, up, smoke).
# Inside make the file wins over a same-named shell variable; write values unquoted (Makefile syntax).
ifneq (,$(wildcard .env))
include .env
export
endif

setup:         ## create .env with a fresh ADMIN_TOKEN (skips an existing file)
	@if [ -e .env ]; then echo ".env exists, skipped"; \
	else token=$$(python3 -c "import secrets; print(secrets.token_urlsafe(32))"); \
	  sed "s|^ADMIN_TOKEN=.*|ADMIN_TOKEN=$$token|" .env.example > .env && echo "created .env"; fi

db:            ## start Postgres only, wait until it accepts connections
	docker compose up -d --wait db

dev-backend:   ## API with reload on :8000
	cd backend && uv run alembic upgrade head && uv run fastapi dev

dev-frontend:  ## Next.js on :3000
	cd frontend && pnpm dev

OPENAPI ?= frontend/openapi.json
SCHEMA ?= frontend/src/lib/api/schema.d.ts

api-types:     ## regenerate frontend types from the backend OpenAPI schema
	cd backend && ADMIN_TOKEN=unused uv run python -c "import json; from app.main import app; print(json.dumps(app.openapi(), indent=2))" > $(abspath $(OPENAPI))
	cd frontend && pnpm exec openapi-typescript $(abspath $(OPENAPI)) -o $(abspath $(SCHEMA))

# Generates into a temp dir, so it passes with regenerated-but-unstaged files (unlike `git diff`).
check-api-types:
	@tmp=$$(mktemp -d) && $(MAKE) -s api-types OPENAPI=$$tmp/openapi.json SCHEMA=$$tmp/schema.d.ts >/dev/null \
	  && diff -q $$tmp/openapi.json $(OPENAPI) && diff -q $$tmp/schema.d.ts $(SCHEMA) \
	  || { echo "Frontend API types are stale: run 'make api-types'"; exit 1; }

migration:     ## make migration m="describe change"
	cd backend && uv run alembic revision --autogenerate -m "$(m)"

migrate:
	cd backend && uv run alembic upgrade head

check: check-backend check-frontend  ## everything the `backend` and `frontend` CI jobs run (CI calls these targets)

check-backend:
	cd backend && uv run ruff format --check . && uv run ruff check . && uv run mypy . && uv run alembic upgrade head && uv run alembic check && uv run pytest

check-frontend: check-api-types
	cd frontend && pnpm lint && pnpm typecheck && pnpm build

audit:         ## known CVEs in runtime deps (own CI workflow, not part of `check`)
	cd backend && uv export --locked --no-dev --no-emit-project -q | uvx pip-audit@2.10.1 -r /dev/stdin --disable-pip --strict
	cd frontend && pnpm audit --prod --audit-level=high

up:            ## full stack in Docker
	docker compose up --build

# Own compose project, so a run never touches the dev stack's volume. Host ports are shared with
# the dev stack: stop it first (a clash fails fast with "port is already allocated").
# The frontend's `/` returns 200 even when its backend call fails, so the page must show the
# seeded device. The seed response holds a device token: never print it.
smoke:         ## build the images, boot the compose stack, assert it works end to end (needs ports 3000/8000/5432 free)
	@set -e; \
	export COMPOSE_PROJECT_NAME=brew-smoke ADMIN_TOKEN=$${ADMIN_TOKEN:-smoke-token}; \
	trap 'rc=$$?; set +e; if [ $$rc -ne 0 ]; then docker compose ps -a; docker compose logs; fi; docker compose down -v --remove-orphans; exit $$rc' EXIT; \
	trap 'exit 130' INT; trap 'exit 143' TERM; \
	docker compose up --build --wait; \
	curl -fsS http://localhost:8000/health >/dev/null; \
	curl -fsS -X POST http://localhost:8000/api/v1/devices \
	  -H "Authorization: Bearer $$ADMIN_TOKEN" -H "Content-Type: application/json" \
	  -d '{"name":"smoke-device","kind":"in_vessel"}' >/dev/null; \
	page=$$(curl -fsS http://localhost:3000/); \
	case "$$page" in *smoke-device*) ;; *) echo "smoke: frontend page is missing smoke-device"; exit 1;; esac; \
	echo "smoke: ok"
