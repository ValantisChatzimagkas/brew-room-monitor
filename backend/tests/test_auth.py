import re

import pytest
from fastapi.routing import iter_route_contexts
from fastapi.testclient import TestClient

from app.main import app
from tests.conftest import LEFTOVER_ADMIN_TOKEN

# Public on purpose. `/docs/oauth2-redirect` is registered by FastAPI together with `/docs`;
# we use bearer auth, so it is never used.
EXEMPT_PATHS = {"/health", "/openapi.json", "/docs", "/docs/oauth2-redirect"}
USER_ROUTES = {
    ("GET", "/api/v1/me"),
    ("POST", "/api/v1/locations"),
    ("POST", "/api/v1/devices"),
    ("PATCH", "/api/v1/devices/{device_id}"),
    ("POST", "/api/v1/devices/{device_id}/revoke"),
    ("POST", "/api/v1/devices/{device_id}/rotate"),
    ("POST", "/api/v1/batches"),
    ("PATCH", "/api/v1/batches/{batch_id}"),
    ("GET", "/api/v1/devices"),
    ("GET", "/api/v1/locations"),
    ("GET", "/api/v1/readings"),
    ("GET", "/api/v1/batches"),
    ("GET", "/api/v1/batches/{batch_id}"),
}
# A route listed in no table must reject every token kind.
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


def _allowed_kinds(method: str, path: str) -> set[str]:
    route = (method, path)
    if route in USER_ROUTES:
        return {"user"}
    return {"device"} if route in DEVICE_ROUTES else set()


def test_every_route_requires_its_token(
    client: TestClient,
    device_headers: dict[str, str],
    user_headers: dict[str, str],
) -> None:
    own_headers = {"device": device_headers, "user": user_headers}
    unknown_401 = client.get("/api/v1/me", headers={"Authorization": "Bearer nope"})
    assert unknown_401.status_code == 401
    routes = _protected_routes()
    assert routes, "no routes found; the route walk is broken"

    for method, path in routes:
        allowed = _allowed_kinds(method, path)
        wrong_kinds = {k: h for k, h in own_headers.items() if k not in allowed}
        url = re.sub(r"\{[^}]+\}", "1", path)
        # An empty body is on purpose: auth must run before body validation.
        for label, headers in (
            ("no token", {}),
            ("unknown token", {"Authorization": "Bearer nope"}),
            ("former admin token", {"Authorization": f"Bearer {LEFTOVER_ADMIN_TOKEN}"}),
            *((f"{k} token", h) for k, h in wrong_kinds.items()),
        ):
            res = client.request(method, url, json={}, headers=headers)
            assert res.status_code == 401, (
                f"{method} {path} with {label} returned {res.status_code}"
            )
            assert res.json() == unknown_401.json(), f"{method} {path} with {label}"
