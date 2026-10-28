from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient


def test_ingest_and_list(
    client: TestClient, device_headers: dict[str, str], admin_headers: dict[str, str]
) -> None:
    ts = "2026-01-01T12:00:00+00:00"
    batch = {
        "readings": [
            {"metric": "temperature_c", "value": 18.5, "recorded_at": ts},
            {"metric": "humidity_pct", "value": 61.0},  # no clock on device -> server time
        ]
    }
    res = client.post("/api/v1/readings", json=batch, headers=device_headers)
    assert res.status_code == 201
    assert res.json() == {"accepted": 2}

    temps = client.get(
        "/api/v1/readings", params={"metric": "temperature_c"}, headers=admin_headers
    ).json()
    assert len(temps) == 1
    assert temps[0]["value"] == 18.5
    assert datetime.fromisoformat(temps[0]["recorded_at"]) == datetime.fromisoformat(ts)


def test_ingest_requires_device_token(client: TestClient, admin_headers: dict[str, str]) -> None:
    batch = {"readings": [{"metric": "temperature_c", "value": 20}]}
    assert client.post("/api/v1/readings", json=batch).status_code == 401
    # The admin token is not a device token.
    assert client.post("/api/v1/readings", json=batch, headers=admin_headers).status_code == 401


def test_rejects_bad_payloads(client: TestClient, device_headers: dict[str, str]) -> None:
    future = (datetime.now(UTC) + timedelta(hours=1)).isoformat()
    bad_batches = [
        {"readings": []},
        {"readings": [{"metric": "unknown", "value": 1}]},
        {"readings": [{"metric": "temperature_c", "value": "NaN"}]},
        {"readings": [{"metric": "temperature_c", "value": 1, "recorded_at": "2026-01-01T12:00"}]},
        {"readings": [{"metric": "temperature_c", "value": 1, "recorded_at": future}]},
    ]
    for batch in bad_batches:
        res = client.post("/api/v1/readings", json=batch, headers=device_headers)
        assert res.status_code == 422, batch
