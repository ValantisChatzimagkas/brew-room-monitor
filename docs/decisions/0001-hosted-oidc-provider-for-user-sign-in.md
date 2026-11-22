# 0001: Hosted OIDC provider for user sign-in

Status: accepted.

## Context
Everything hangs on one shared `ADMIN_TOKEN`: the backend knows no users and cannot keep one owner's devices apart from another's. The service will have several owners and later runs on FastAPI Cloud, and we would rather not hold or defend passwords. The follow-ups (verifying JWTs and `/api/v1/me`, owner scoping, frontend login) all read the provider and env var names from here.

## Options
Free-tier facts are as of 2026-11-01, mostly from third-party pages. Re-check each provider's pricing page before relying on them.

| Option | Free tier | Backend verifies from public keys, no secret held | Cost to move away |
|---|---|---|---|
| **Auth0** (chosen) | 25,000 MAU, no time limit | Yes: OIDC discovery + JWKS | Low: standard OIDC, no provider code in the backend |
| Supabase Auth (runner-up) | 50,000 MAU, but free projects pause after 1 week of inactivity, which would take sign-in down | Yes: JWKS | Low for tokens; bundles a Postgres we don't use |
| Clerk | 50,000 monthly retained users | Yes: JWKS | High: SDK-heavy, ~60s session tokens |
| Better Auth in Next.js | Free library | Only if the backend fetches JWKS from the frontend, so the backend depends on the frontend being up | Medium: passwords and signing keys live in a database the frontend would have to reach, a new frontend → database path |
| Passwords in our FastAPI | Free | No: we hold password hashes and signing keys | High: we own the user store and its attack surface |

## Decision
Use Auth0 as the OIDC provider. The backend verifies RS256 access tokens against the issuer's JWKS and checks signature, `iss`, `aud` and `exp`. The user identity key is the `(iss, sub)` pair, never email, so a provider swap or a second issuer cannot merge two people. Standard OIDC/JWT is the swap seam; the backend has no Auth0-specific code.

### Devices and the admin token
- Devices keep their opaque per-device tokens (SHA-256 hash lookup, revoke/rotate). No JWT: flashed devices cannot be updated and cannot run expiry or refresh logic.
- The admin token is transitional. Once owner scoping ships, locations are created, and devices are registered, updated, revoked and rotated, only with a user JWT, so every device has an owner; an admin call carries no user and would need an act-as-user path, which is roles and out of scope. Until the frontend login ships and moves it to user tokens, the admin token keeps the unscoped devices, locations and readings list reads, and it keeps the batch routes until batches are scoped through their device's owner. It is retired once no route needs it.

### Env vars (names only, never values)
- Backend: `AUTH_ISSUER` (must equal the token's `iss` exactly, trailing slash included; Auth0's ends in `/`) and `AUTH_AUDIENCE`. The JWKS URL comes from the issuer's OIDC discovery document, so there is no JWKS var. RS256 is a code constant, not env, so a token cannot choose its own algorithm. The backend holds no password or signing secret.
- Set both or neither. Required in production. With them unset the app still boots, but every user-JWT route returns the generic 401 in every environment (fail closed): "unset" never means "skip verification".
- Frontend: a confidential Auth0 client with a server-side session cookie, so the browser never sees a token and the Next.js server calls the backend with the user's access token. All server-side, never `NEXT_PUBLIC_*`: the SDK's domain, client id, client secret, session-encryption secret and app base URL, plus the API audience (same value as `AUTH_AUDIENCE`). The frontend must request that audience, or Auth0 issues no JWT access token for the API. The frontend login work pins the exact SDK variable names.

## Consequences
- A provider outage stops user sign-in and, once cached signing keys or sessions run out (a cold stateless instance must fetch the JWKS first), user API calls. Device ingest is never affected.
- The free-tier cap and Auth0's behaviour when it is exceeded are unconfirmed; check before launch.
- Tests mint tokens against a local fake issuer (`backend/CLAUDE.md`); local dev uses a dev tenant's test token.
- Moving away means changing `AUTH_*` and the frontend SDK, re-importing users (an Auth0 password-hash export needs a support request) and remapping `User` rows keyed by `(iss, sub)`. Supabase Auth is the fallback.

## Supersedes
Nothing yet. These stay true until the named tickets ship, and those tickets update them:
- JWT verification and frontend login: `ARCHITECTURE.md` ("The browser never calls the backend", "Two token kinds" say there is no user auth), the auth guardrails in root `CLAUDE.md` and `frontend/CLAUDE.md`. `frontend/CLAUDE.md` also says `client.ts` is the only file that reads `process.env`; the Auth0 SDK reads its own env vars, so the frontend login work must amend that rule or load the config through `client.ts`.
- Owner scoping: the registration flow in the `ARCHITECTURE.md` diagram and its "registered through the admin API directly" line, and the `curl` with `$ADMIN_TOKEN` in `firmware/README.md`.
