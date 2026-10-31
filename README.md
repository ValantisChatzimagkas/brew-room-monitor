# Brew Room Monitor

Ambient conditions of the brewing room(s) and yeast insights, fed by ESP32 / in-vessel sensors.

**Stack:** FastAPI · SQLModel · Alembic · Postgres · Next.js · Tailwind · shadcn/ui · Docker

## Quick start

Needs Docker, [uv](https://docs.astral.sh/uv/), Node 22 + pnpm.

```sh
make setup                      # .env from .env.example, with a generated ADMIN_TOKEN
make dev                        # Postgres + API (:8000/docs) + frontend (:3000); Ctrl-C stops the servers, Postgres stays up
```

Run the pieces in separate terminals with `make db`, `make dev-backend` and `make dev-frontend`. Full stack in containers: `make up`. All targets: `make help`.

`make down` stops the compose stack, `make logs` tails it, `make db-reset` wipes the dev database (after you type `yes`).

Register a sensor and send data: see [`firmware/README.md`](firmware/README.md).

## Before pushing

`make check` (the backend and frontend CI jobs). `make smoke` builds the images and boots the full stack (its own CI job; needs Docker and ports 3000/8000/5432 free). `make audit` checks dependencies for known CVEs (its own CI workflow, also weekly).

How it fits together and why: [`ARCHITECTURE.md`](ARCHITECTURE.md). Working rules for humans and AI agents: [`CLAUDE.md`](CLAUDE.md).
