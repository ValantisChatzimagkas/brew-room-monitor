from typing import Any

import pytest
from fastapi.testclient import TestClient


@pytest.mark.parametrize(
    ("method", "path"),
    [
        ("GET", "/api/v1/devices"),
        ("POST", "/api/v1/devices"),
        ("PATCH", "/api/v1/devices/1"),
        ("POST", "/api/v1/devices/1/revoke"),
    ],
)
def test_requires_admin_token(
    client: TestClient, device_headers: dict[str, str], method: str, path: str
) -> None:
    # Missing, unknown, and a valid device token (wrong kind) are all rejected.
    for headers in ({}, {"Authorization": "Bearer nope"}, device_headers):
        assert client.request(method, path, json={}, headers=headers).status_code == 401


def test_create_returns_token_once(
    client: TestClient, admin_headers: dict[str, str], location_id: int
) -> None:
    res = client.post(
        "/api/v1/devices",
        json={"name": "room-a", "kind": "ambient", "location_id": location_id},
        headers=admin_headers,
    )
    assert res.status_code == 201
    assert res.json()["token"]

    listed = client.get("/api/v1/devices", headers=admin_headers).json()
    assert [d["name"] for d in listed] == ["room-a"]
    assert listed[0]["location"] == {"id": location_id, "name": "garage"}
    assert "token" not in listed[0] and "token_hash" not in listed[0]
    assert listed[0]["revoked_at"] is None


def test_create_location_rules(
    client: TestClient, admin_headers: dict[str, str], location_id: int
) -> None:
    cases: list[tuple[dict[str, Any], int]] = [
        ({"name": "a", "kind": "ambient"}, 422),
        ({"name": "b", "kind": "ambient", "location_id": None}, 422),
        ({"name": "c", "kind": "ambient", "location_id": 999}, 422),
        ({"name": "d", "kind": "in_vessel", "location_id": 999}, 422),
        ({"name": "e", "kind": "in_vessel"}, 201),
        ({"name": "f", "kind": "in_vessel", "location_id": location_id}, 201),
    ]
    for body, expected in cases:
        res = client.post("/api/v1/devices", json=body, headers=admin_headers)
        assert res.status_code == expected, body


def test_duplicate_name_conflicts(client: TestClient, admin_headers: dict[str, str]) -> None:
    body = {"name": "dup", "kind": "in_vessel"}
    assert client.post("/api/v1/devices", json=body, headers=admin_headers).status_code == 201
    assert client.post("/api/v1/devices", json=body, headers=admin_headers).status_code == 409


def test_update_renames_and_moves(
    client: TestClient, admin_headers: dict[str, str], location_id: int
) -> None:
    device = client.post(
        "/api/v1/devices",
        json={"name": "room-a", "kind": "ambient", "location_id": location_id},
        headers=admin_headers,
    ).json()
    cellar = client.post("/api/v1/locations", json={"name": "cellar"}, headers=admin_headers)

    res = client.patch(
        f"/api/v1/devices/{device['id']}",
        json={"name": "room-b", "location_id": cellar.json()["id"]},
        headers=admin_headers,
    )
    assert res.status_code == 200
    listed = client.get("/api/v1/devices", headers=admin_headers).json()
    assert [(d["name"], d["location"]["name"]) for d in listed] == [("room-b", "cellar")]


def test_rejects_bad_updates(
    client: TestClient, admin_headers: dict[str, str], location_id: int
) -> None:
    ambient = client.post(
        "/api/v1/devices",
        json={"name": "room-a", "kind": "ambient", "location_id": location_id},
        headers=admin_headers,
    ).json()
    client.post(
        "/api/v1/devices", json={"name": "taken", "kind": "in_vessel"}, headers=admin_headers
    )
    path = f"/api/v1/devices/{ambient['id']}"

    cases: list[tuple[str, dict[str, Any], int]] = [
        (path, {"name": "taken"}, 409),
        (path, {"location_id": None}, 422),
        (path, {"location_id": 999}, 422),
        (path, {"name": ""}, 422),
        (path, {"name": "x" * 65}, 422),
        (path, {"name": None}, 422),
    ]
    for target, body, expected in cases:
        res = client.patch(target, json=body, headers=admin_headers)
        assert res.status_code == expected, (target, body)


@pytest.mark.parametrize(
    ("method", "path", "body"),
    [
        ("PATCH", "/api/v1/devices/999", {"name": "x"}),
        ("POST", "/api/v1/devices/999/revoke", None),
    ],
)
def test_unknown_device_404(
    client: TestClient, admin_headers: dict[str, str], method: str, path: str, body: Any
) -> None:
    assert client.request(method, path, json=body, headers=admin_headers).status_code == 404


def test_revoke_cuts_off_device(client: TestClient, admin_headers: dict[str, str]) -> None:
    device = client.post(
        "/api/v1/devices", json={"name": "capsule", "kind": "in_vessel"}, headers=admin_headers
    ).json()
    token = {"Authorization": f"Bearer {device['token']}"}
    batch = {"readings": [{"metric": "temperature_c", "value": 18.0}]}
    # Out of range: a revoked token must get 401 before the body is validated.
    bad_batch = {"readings": [{"metric": "temperature_c", "value": 200}]}
    assert client.post("/api/v1/readings", json=batch, headers=token).status_code == 201

    path = f"/api/v1/devices/{device['id']}/revoke"
    res = client.post(path, headers=admin_headers)
    assert res.status_code == 200
    revoked_at = res.json()["revoked_at"]
    assert revoked_at is not None
    assert client.post(path, headers=admin_headers).json()["revoked_at"] == revoked_at

    cut_off = client.post("/api/v1/readings", json=bad_batch, headers=token)
    unknown = client.post(
        "/api/v1/readings", json=bad_batch, headers={"Authorization": "Bearer nope"}
    )
    assert cut_off.status_code == 401
    assert cut_off.json() == unknown.json()

    readings = client.get("/api/v1/readings", headers=admin_headers).json()
    assert [r["device_id"] for r in readings] == [device["id"]]
    listed = client.get("/api/v1/devices", headers=admin_headers).json()
    assert listed[0]["revoked_at"] == revoked_at
    assert "token" not in listed[0] and "token_hash" not in listed[0]


def test_in_vessel_location_can_be_cleared(
    client: TestClient, admin_headers: dict[str, str], location_id: int
) -> None:
    device = client.post(
        "/api/v1/devices",
        json={"name": "capsule", "kind": "in_vessel", "location_id": location_id},
        headers=admin_headers,
    ).json()
    res = client.patch(
        f"/api/v1/devices/{device['id']}", json={"location_id": None}, headers=admin_headers
    )
    assert res.status_code == 200
    assert res.json()["location"] is None


def test_list_limit(client: TestClient, admin_headers: dict[str, str]) -> None:
    for name in ("a", "b"):
        client.post(
            "/api/v1/devices", json={"name": name, "kind": "in_vessel"}, headers=admin_headers
        )
    res = client.get("/api/v1/devices", params={"limit": 1}, headers=admin_headers)
    assert [d["name"] for d in res.json()] == ["a"]
    for limit in (0, 501):
        res = client.get("/api/v1/devices", params={"limit": limit}, headers=admin_headers)
        assert res.status_code == 422, limit
