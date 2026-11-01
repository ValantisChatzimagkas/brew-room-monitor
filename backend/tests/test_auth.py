import re

import pytest
from fastapi.routing import iter_route_contexts
from fastapi.testclient import TestClient

from app.main import app

# Public on purpose. `/docs/oauth2-redirect` is registered by FastAPI together with `/docs`;
# we use bearer auth, so it is never used.
EXEMPT_PATHS = {"/health", "/openapi.json", "/docs", "/docs/oauth2-redirect"}
USER_ROUTES = {("GET", "/api/v1/me")}
# Every route not listed here or in DEVICE_ROUTES is admin-only.
DEVICE_ROUTES = {("POST", "/api/v1/readings")}


def _protected_routes() -> list[tuple[str, str]]:
    routes: set[tuple[str, str]] = set()
    for context in iter_route_contexts(app.routes):
        if context.path in EXEMPT_PATHS:
            continue
        if context.path is None or context.methods is None:
            pytest.fail(
                f"unsupported route type at {context.path!r}: extend test_auth.py or exempt it"
            )
        routes.update((method, context.path) for method in context.methods)
    return sorted(routes)


def _kind(method: str, path: str) -> str:
    if (method, path) in USER_ROUTES:
        return "user"
    return "device" if (method, path) in DEVICE_ROUTES else "admin"


def test_every_route_requires_its_token(
    client: TestClient,
    admin_headers: dict[str, str],
    device_headers: dict[str, str],
    user_headers: dict[str, str],
) -> None:
    own_headers = {"admin": admin_headers, "device": device_headers, "user": user_headers}
    routes = _protected_routes()
    assert routes, "no routes found; the route walk is broken"

    for method, path in routes:
        kind = _kind(method, path)
        wrong_kinds = {k: h for k, h in own_headers.items() if k != kind}
        url = re.sub(r"\{[^}]+\}", "1", path)
        # An empty body is on purpose: auth must run before body validation.
        for label, headers in (
            ("no token", {}),
            ("unknown token", {"Authorization": "Bearer nope"}),
            *((f"{k} token", h) for k, h in wrong_kinds.items()),
        ):
            res = client.request(method, url, json={}, headers=headers)
            assert res.status_code == 401, (
                f"{method} {path} with {label} returned {res.status_code}"
            )
