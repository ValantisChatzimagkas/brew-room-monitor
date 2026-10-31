from fastapi.testclient import TestClient


def test_create_and_list(client: TestClient, admin_headers: dict[str, str]) -> None:
    res = client.post("/api/v1/locations", json={"name": "  Garage "}, headers=admin_headers)
    assert res.status_code == 201
    assert res.json()["name"] == "Garage"

    listed = client.get("/api/v1/locations", headers=admin_headers).json()
    assert listed == [res.json()]


def test_rejects_bad_names(client: TestClient, admin_headers: dict[str, str]) -> None:
    client.post("/api/v1/locations", json={"name": "Garage"}, headers=admin_headers)
    cases = [
        ("garage", 409),
        (" GARAGE ", 409),
        ("", 422),
        ("   ", 422),
        ("x" * 65, 422),
    ]
    for name, expected in cases:
        res = client.post("/api/v1/locations", json={"name": name}, headers=admin_headers)
        assert res.status_code == expected, name


def test_list_limit(client: TestClient, admin_headers: dict[str, str]) -> None:
    for name in ("a", "b"):
        client.post("/api/v1/locations", json={"name": name}, headers=admin_headers)
    res = client.get("/api/v1/locations", params={"limit": 1}, headers=admin_headers)
    assert [loc["name"] for loc in res.json()] == ["a"]
    for limit in (0, 501):
        res = client.get("/api/v1/locations", params={"limit": limit}, headers=admin_headers)
        assert res.status_code == 422, limit
