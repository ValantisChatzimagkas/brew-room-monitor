# Architecture

How the parts fit together and why. Rules for working inside each part live in the `CLAUDE.md` files; this is the map. It describes things that change rarely: if you change a boundary or a flow below, update this file in the same commit.

## Bird's-eye view

```
ESP32 / capsule ──device token──▶ POST /api/v1/readings ─┐
laptop (curl)   ──admin token───▶ POST /api/v1/devices  ─┼─▶ FastAPI ──▶ Postgres
browser ──▶ Next.js server ──admin token──▶ GET /api/v1/* ─┘
```

Devices push batches of readings. The backend stores them as rows of `(device, metric, value, recorded_at)`. The Next.js server reads them and renders HTML. The browser only ever talks to Next.js.

## Codemap

Start reading here, by flow:

- **Register a device:** `backend/app/routers/locations.py` creates the room, then `backend/app/routers/devices.py` creates the device pointing at it plus a random token, stores only its hash (`app/security.py`), and returns the plaintext once.
- **Ingest:** `backend/app/routers/readings.py` `ingest_readings`. Auth comes from `current_device` in `app/deps.py` (token hash lookup). Payload bounds are in `ReadingBatch` / `ReadingIn`, metrics and units in `Metric` (`app/models.py`), the future-timestamp check in `MAX_CLOCK_SKEW`.
- **Show:** `frontend/src/app/page.tsx` → `getApi()` in `frontend/src/lib/api/client.ts` → `GET /api/v1/devices` and `/readings` with the admin token.
- **Contract:** FastAPI generates OpenAPI → `make api-types` → `frontend/openapi.json` + `frontend/src/lib/api/schema.d.ts`. The device-facing part is written down in `firmware/README.md`.
- **Schema:** `backend/app/models.py` → Alembic migrations in `backend/alembic/versions/`.
- **Run/deploy:** `docker-compose.yml` (db, backend, frontend), one `Dockerfile` per app, CI in `.github/workflows/ci.yml`.

## Boundaries and why they exist

- **The browser never calls the backend.** The admin token lives only on the Next.js server (`server-only` client). So the backend needs no CORS, no sessions and no user auth. Its callers are devices and admin. The only unauthenticated routes are `GET /health` and the OpenAPI schema (`/openapi.json` stays public in production; `/docs` doesn't).
- **Two token kinds.** Admin is one shared secret held by servers. Each device gets its own random token, stored as a SHA-256 hash. A leaked device token only affects that one device, and a database leak doesn't expose usable tokens. A fast hash is enough because the tokens are 256-bit random, not passwords.
- **Plain HTTP on a trusted LAN only.** Tokens cross the network in cleartext, so put TLS in front (reverse proxy or tunnel) before the backend is reachable from outside the LAN. Postgres is bound to localhost in `docker-compose.yml` for the same reason.
- **Read-only frontend, frozen `/api/v1`, generated frontend types:** rules and reasons are in the root `CLAUDE.md` guardrails. What that means for the system's shape: devices are registered through the admin API directly (`firmware/README.md`), not from the UI.

## Data model and why

- **One narrow `reading` table** (device, metric, value, time), not a column per sensor. A new metric is a new `Metric` value, not a new table or column, and because metrics are stored as strings it needs no migration.
- **A location is a room, as its own row** (name unique ignoring case), so devices in the same room group reliably and a device moves by changing `location_id`. `ambient` devices must have one; `in_vessel` devices may omit it, because their place will come from the vessel/batch they float in. The FK is `RESTRICT`, so a location with devices can't vanish.
- **Two timestamps.** `recorded_at` comes from the device (optional, because a device without NTP/RTC omits it and the server stamps the receive time). `received_at` is always server time. Timestamps clearly in the future are rejected, not stored, so a bad device clock can't corrupt history.
- **Batched ingest** (bounds in `firmware/README.md`), because sending every few minutes saves device battery.
- **Ingest is idempotent.** A device-stamped reading is stored once per `(device, metric, recorded_at)`; a resend is a no-op, so a device that lost a 201 can retry its buffer. Readings without `recorded_at` are exempt, because they share the receive time and would clash. A partial unique index on `Reading` enforces it (`backend/app/models.py`).
- **Index `(device_id, metric, recorded_at)`** serves per-device and per-metric history; a second, partial unique index on the same columns does the dedupe. The dashboard's current query (all readings, newest first) doesn't filter on those columns, so it can't use this index; add a `recorded_at` index if that query gets slow.

## Runtime and deploy

- **Sync endpoints, sync SQLModel session.** Simple and enough for this load; FastAPI runs them in its threadpool.
- **The backend is stateless and configured only by env**, so the same code runs in Docker or on FastAPI Cloud.
- **Migrations run on container start** (`backend/Dockerfile`). That's fine for one instance; move them to a release step before running more than one.
- **The frontend reads env at request time**, not build time, so one image works in every environment.
- **Postgres only, no cache or queue.** Add one when a measured need shows up.

## Extending it

- **New metric:** add a `Metric` value → `make api-types` → add its label in `METRIC_LABEL` in `page.tsx` (typecheck forces this) → list it in `firmware/README.md`.
- **New device type:** add a `DeviceKind` value if it differs from the existing ones. If it can't send the v1 payload, see `firmware/README.md` (Hardware notes) and the `/api/v1` guardrail.
