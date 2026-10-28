.PHONY: db dev-backend dev-frontend api-types check-api-types migration migrate check check-backend check-frontend audit up

db:            ## start Postgres only
	docker compose up -d db

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

check: check-backend check-frontend  ## everything the CI build job runs (CI calls these targets)

check-backend:
	cd backend && uv run ruff format --check . && uv run ruff check . && uv run mypy . && uv run alembic upgrade head && uv run alembic check && uv run pytest

check-frontend: check-api-types
	cd frontend && pnpm lint && pnpm typecheck && pnpm build

audit:         ## known CVEs in runtime deps (own CI workflow, not part of `check`)
	cd backend && uv export --locked --no-dev --no-emit-project -q | uvx pip-audit@2.10.1 -r /dev/stdin --disable-pip --strict
	cd frontend && pnpm audit --prod --audit-level=high

up:            ## full stack in Docker
	docker compose up --build
