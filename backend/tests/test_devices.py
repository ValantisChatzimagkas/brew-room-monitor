from fastapi.testclient import TestClient


def test_requires_admin_token(client: TestClient) -> None:
    assert client.get("/api/v1/devices").status_code == 401
    bad = {"Authorization": "Bearer nope"}
    assert client.get("/api/v1/devices", headers=bad).status_code == 401


def test_create_returns_token_once(client: TestClient, admin_headers: dict[str, str]) -> None:
    res = client.post(
        "/api/v1/devices",
        json={"name": "fermenter-a", "kind": "in_vessel", "location": "cellar"},
        headers=admin_headers,
    )
    assert res.status_code == 201
    assert res.json()["token"]

    listed = client.get("/api/v1/devices", headers=admin_headers).json()
    assert [d["name"] for d in listed] == ["fermenter-a"]
    assert "token" not in listed[0] and "token_hash" not in listed[0]


def test_duplicate_name_conflicts(client: TestClient, admin_headers: dict[str, str]) -> None:
    body = {"name": "dup", "kind": "ambient"}
    assert client.post("/api/v1/devices", json=body, headers=admin_headers).status_code == 201
    assert client.post("/api/v1/devices", json=body, headers=admin_headers).status_code == 409
