# Brew Room Monitor

[![CI](https://github.com/ValantisChatzimagkas/brew-room-monitor/actions/workflows/ci.yml/badge.svg)](https://github.com/ValantisChatzimagkas/brew-room-monitor/actions/workflows/ci.yml)

A service for monitoring brewing rooms. Sensor devices such as ESP32 boards push ambient and in-vessel readings to an HTTP API, and a web dashboard shows each room's current conditions and history. It exists to make fermentation conditions visible without hand-logging them, with a device contract simple enough for battery-powered hardware that buffers and retries.

## Features

- Token-authenticated reading ingest with per-metric validation, idempotent retries and offline-buffer backfill ([device contract](firmware/README.md)).
- Device registration, revocation and token rotation; device tokens are stored hashed.
- Locations and fermentation batches, with a per-device no-overlap constraint and readings filterable by batch, and per-batch condition summaries, and an optional yeast temperature range per batch with the time its readings spent below, inside and above it.
- Dashboard grouped by room with reading freshness, plus a device page with per-metric history charts and the device's recent batches with their condition summaries and yeast-range split, time out of range flagged.
- Sign-in with a hosted OIDC provider (Auth0), or the bundled local provider in dev: the dashboard needs a login and shows only the signed-in user's devices; the backend verifies the user's JWT on user routes (`/api/v1/me`).

## Stack

FastAPI, SQLModel, Alembic and Postgres on the backend; Next.js, Tailwind and shadcn/ui on the frontend; Docker Compose; GitHub Actions CI. The repo does not include device firmware, only the API contract it must follow.

## Quick start

Needs Docker, [uv](https://docs.astral.sh/uv/), Python 3, Node 22 + pnpm.

```sh
make setup                      # .env from .env.example, with a new session secret and sign-in key
make dev                        # Postgres + API (:8000/docs) + frontend (:3000); Ctrl-C stops the servers, Postgres stays up
```

Sign-in uses a local OIDC provider that `make dev` and `make up` start: type any username in its form; the same name is the same user. If `oidc.localhost` doesn't resolve on your machine, add `127.0.0.1 oidc.localhost` to `/etc/hosts` (`make oidc` tells you).

To use a real Auth0 tenant instead, create a Regular Web Application (callback `<APP_BASE_URL>/auth/callback`, logout URL `<APP_BASE_URL>`) and an API whose identifier is `AUTH_AUDIENCE`, and put their values in `.env` (names in `.env.example`; background in [ADR 0001](docs/decisions/0001-hosted-oidc-provider-for-user-sign-in.md)). There is no dev bypass: `make dev`, `make dev-frontend` and `make up` refuse to start and name any that are missing.

Run the pieces in separate terminals with `make db`, `make dev-backend` and `make dev-frontend`. Full stack in containers: `make up`. All targets: `make help`.

`make down` stops the compose stack, `make logs` tails it, `make db-reset` wipes the dev database (after you type `yes`).

Register a device and send data: see [`firmware/README.md`](firmware/README.md).

## Before pushing

`make check` (the backend and frontend CI jobs). `make smoke` builds the images and boots the full stack (its own CI job; needs Docker and ports 3000/8000/5432 free). `make audit` checks dependencies for known CVEs (its own CI workflow, also weekly).

How it fits together and why: [`ARCHITECTURE.md`](ARCHITECTURE.md). Working rules for humans and AI agents: [`CLAUDE.md`](CLAUDE.md).

## License

[MIT](LICENSE)
