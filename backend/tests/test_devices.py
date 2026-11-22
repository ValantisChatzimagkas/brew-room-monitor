from typing import Any

import pytest
from fastapi.testclient import TestClient


def test_create_returns_token_once(
    client: TestClient,
    admin_headers: dict[str, str],
    user_headers: dict[str, str],
    location_id: int,
) -> None:
    res = client.post(
        "/api/v1/devices",
        json={"name": "room-a", "kind": "ambient", "location_id": location_id},
        headers=user_headers,
    )
    assert res.status_code == 201
    assert res.json()["token"]

    listed = client.get("/api/v1/devices", headers=admin_headers).json()
    assert [d["name"] for d in listed] == ["room-a"]
    assert listed[0]["location"] == {"id": location_id, "name": "garage"}
    assert "token" not in listed[0] and "token_hash" not in listed[0]
    assert listed[0]["revoked_at"] is None


def test_create_location_rules(
    client: TestClient, user_headers: dict[str, str], location_id: int
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
        res = client.post("/api/v1/devices", json=body, headers=user_headers)
        assert res.status_code == expected, body


def test_names_are_unique_per_owner(
    client: TestClient, user_headers: dict[str, str], other_user_headers: dict[str, str]
) -> None:
    body = {"name": "room-a", "kind": "in_vessel"}
    assert client.post("/api/v1/devices", json=body, headers=user_headers).status_code == 201
    assert client.post("/api/v1/devices", json=body, headers=other_user_headers).status_code == 201
    assert client.post("/api/v1/devices", json=body, headers=user_headers).status_code == 409


def test_update_renames_and_moves(
    client: TestClient,
    admin_headers: dict[str, str],
    user_headers: dict[str, str],
    location_id: int,
) -> None:
    device = client.post(
        "/api/v1/devices",
        json={"name": "room-a", "kind": "ambient", "location_id": location_id},
        headers=user_headers,
    ).json()
    cellar = client.post("/api/v1/locations", json={"name": "cellar"}, headers=user_headers)

    res = client.patch(
        f"/api/v1/devices/{device['id']}",
        json={"name": "room-b", "location_id": cellar.json()["id"]},
        headers=user_headers,
    )
    assert res.status_code == 200
    listed = client.get("/api/v1/devices", headers=admin_headers).json()
    assert [(d["name"], d["location"]["name"]) for d in listed] == [("room-b", "cellar")]


def test_rejects_bad_updates(
    client: TestClient, user_headers: dict[str, str], location_id: int
) -> None:
    ambient = client.post(
        "/api/v1/devices",
        json={"name": "room-a", "kind": "ambient", "location_id": location_id},
        headers=user_headers,
    ).json()
    client.post(
        "/api/v1/devices", json={"name": "taken", "kind": "in_vessel"}, headers=user_headers
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
        res = client.patch(target, json=body, headers=user_headers)
        assert res.status_code == expected, (target, body)


@pytest.mark.parametrize(
    ("method", "path", "body"),
    [
        ("PATCH", "/api/v1/devices/999", {"name": "x"}),
        ("POST", "/api/v1/devices/999/revoke", None),
        ("POST", "/api/v1/devices/999/rotate", None),
    ],
)
def test_unknown_device_404(
    client: TestClient, user_headers: dict[str, str], method: str, path: str, body: Any
) -> None:
    assert client.request(method, path, json=body, headers=user_headers).status_code == 404


def test_revoke_cuts_off_device(
    client: TestClient, admin_headers: dict[str, str], user_headers: dict[str, str]
) -> None:
    device = client.post(
        "/api/v1/devices", json={"name": "capsule", "kind": "in_vessel"}, headers=user_headers
    ).json()
    token = {"Authorization": f"Bearer {device['token']}"}
    batch = {"readings": [{"metric": "temperature_c", "value": 18.0}]}
    # Out of range: a revoked token must get 401 before the body is validated.
    bad_batch = {"readings": [{"metric": "temperature_c", "value": 200}]}
    assert client.post("/api/v1/readings", json=batch, headers=token).status_code == 201

    path = f"/api/v1/devices/{device['id']}/revoke"
    res = client.post(path, headers=user_headers)
    assert res.status_code == 200
    revoked_at = res.json()["revoked_at"]
    assert revoked_at is not None
    assert client.post(path, headers=user_headers).json()["revoked_at"] == revoked_at

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


def test_rotate_replaces_token(client: TestClient, user_headers: dict[str, str]) -> None:
    device = client.post(
        "/api/v1/devices", json={"name": "capsule", "kind": "in_vessel"}, headers=user_headers
    ).json()
    batch = {"readings": [{"metric": "temperature_c", "value": 18.0}]}

    def ingest(token: str) -> int:
        headers = {"Authorization": f"Bearer {token}"}
        return client.post("/api/v1/readings", json=batch, headers=headers).status_code

    def rotate() -> dict[str, Any]:
        res = client.post(f"/api/v1/devices/{device['id']}/rotate", headers=user_headers)
        assert res.status_code == 200
        assert res.json()["revoked_at"] is None
        return dict(res.json())

    token_a = device["token"]
    token_b = rotate()["token"]
    assert token_b != token_a
    assert (ingest(token_a), ingest(token_b)) == (401, 201)

    # Rotating a revoked device re-enables it, and only the newest token works.
    client.post(f"/api/v1/devices/{device['id']}/revoke", headers=user_headers)
    token_c = rotate()["token"]
    assert (ingest(token_b), ingest(token_c)) == (401, 201)


def test_in_vessel_location_can_be_cleared(
    client: TestClient, user_headers: dict[str, str], location_id: int
) -> None:
    device = client.post(
        "/api/v1/devices",
        json={"name": "capsule", "kind": "in_vessel", "location_id": location_id},
        headers=user_headers,
    ).json()
    res = client.patch(
        f"/api/v1/devices/{device['id']}", json={"location_id": None}, headers=user_headers
    )
    assert res.status_code == 200
    assert res.json()["location"] is None


def test_list_limit(
    client: TestClient, admin_headers: dict[str, str], user_headers: dict[str, str]
) -> None:
    for name in ("a", "b"):
        client.post(
            "/api/v1/devices", json={"name": name, "kind": "in_vessel"}, headers=user_headers
        )
    res = client.get("/api/v1/devices", params={"limit": 1}, headers=admin_headers)
    assert [d["name"] for d in res.json()] == ["a"]
    for limit in (0, 501):
        res = client.get("/api/v1/devices", params={"limit": limit}, headers=admin_headers)
        assert res.status_code == 422, limit


def test_owners_cannot_see_each_others_devices(
    client: TestClient, user_headers: dict[str, str], other_user_headers: dict[str, str]
) -> None:
    alice_location = client.post(
        "/api/v1/locations", json={"name": "garage"}, headers=user_headers
    ).json()["id"]
    alice_device = client.post(
        "/api/v1/devices",
        json={"name": "room-a", "kind": "ambient", "location_id": alice_location},
        headers=user_headers,
    ).json()["id"]

    assert client.get("/api/v1/devices", headers=other_user_headers).json() == []
    assert client.get("/api/v1/locations", headers=other_user_headers).json() == []

    # A foreign row answers exactly like a missing one: nothing reveals that it exists.
    for method, suffix, body in [
        ("PATCH", "", {"name": "x"}),
        ("POST", "/revoke", None),
        ("POST", "/rotate", None),
    ]:
        foreign = client.request(
            method, f"/api/v1/devices/{alice_device}{suffix}", json=body, headers=other_user_headers
        )
        missing = client.request(
            method, f"/api/v1/devices/999{suffix}", json=body, headers=other_user_headers
        )
        assert foreign.status_code == 404, (method, suffix)
        assert (foreign.status_code, foreign.json()) == (missing.status_code, missing.json())

    # Neither a new device nor an existing one of bob's can point at alice's location.
    bob_device = client.post(
        "/api/v1/devices", json={"name": "vessel", "kind": "in_vessel"}, headers=other_user_headers
    ).json()["id"]
    for res, unknown in [
        (
            client.post(
                "/api/v1/devices",
                json={"name": "x", "kind": "in_vessel", "location_id": alice_location},
                headers=other_user_headers,
            ),
            client.post(
                "/api/v1/devices",
                json={"name": "x", "kind": "in_vessel", "location_id": 999},
                headers=other_user_headers,
            ),
        ),
        (
            client.patch(
                f"/api/v1/devices/{bob_device}",
                json={"location_id": alice_location},
                headers=other_user_headers,
            ),
            client.patch(
                f"/api/v1/devices/{bob_device}",
                json={"location_id": 999},
                headers=other_user_headers,
            ),
        ),
    ]:
        assert res.status_code == 422
        assert (res.status_code, res.json()) == (unknown.status_code, unknown.json())

    mine = client.get("/api/v1/devices", headers=user_headers).json()
    assert [(d["id"], d["name"]) for d in mine] == [(alice_device, "room-a")]
    renamed = client.patch(
        f"/api/v1/devices/{alice_device}", json={"name": "room-b"}, headers=user_headers
    )
    assert renamed.status_code == 200


def test_admin_lists_everything_unscoped(
    client: TestClient,
    admin_headers: dict[str, str],
    user_headers: dict[str, str],
    other_user_headers: dict[str, str],
) -> None:
    for headers, name in [(user_headers, "a"), (other_user_headers, "b")]:
        client.post("/api/v1/locations", json={"name": name}, headers=headers)
        client.post("/api/v1/devices", json={"name": name, "kind": "in_vessel"}, headers=headers)
    devices = client.get("/api/v1/devices", headers=admin_headers).json()
    locations = client.get("/api/v1/locations", headers=admin_headers).json()
    assert [d["name"] for d in devices] == ["a", "b"]
    assert [loc["name"] for loc in locations] == ["a", "b"]
