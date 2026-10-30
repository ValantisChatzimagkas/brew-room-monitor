from datetime import UTC, datetime, timedelta

import pytest
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
        {"readings": [{"metric": "temperature_c", "value": 1}] * 501},
    ]
    for batch in bad_batches:
        res = client.post("/api/v1/readings", json=batch, headers=device_headers)
        assert res.status_code == 422, batch


def test_resend_is_idempotent(
    client: TestClient, device_headers: dict[str, str], admin_headers: dict[str, str]
) -> None:
    def reading(minute: int) -> dict[str, object]:
        return {
            "metric": "temperature_c",
            "value": 18.0 + minute,
            "recorded_at": f"2026-01-01T12:0{minute}:00Z",
        }

    def stored() -> int:
        return len(client.get("/api/v1/readings", headers=admin_headers).json())

    first = {"readings": [reading(0), reading(1)]}
    for _ in range(2):  # the second round is a retry after a lost 201
        res = client.post("/api/v1/readings", json=first, headers=device_headers)
        assert res.status_code == 201
        assert res.json() == {"accepted": 2}
        assert stored() == 2

    overlapping = {"readings": [reading(1), reading(2)]}
    res = client.post("/api/v1/readings", json=overlapping, headers=device_headers)
    assert res.status_code == 201
    assert res.json() == {"accepted": 2}
    assert stored() == 3


def test_same_reading_from_two_devices_is_stored_twice(
    client: TestClient,
    device_headers: dict[str, str],
    admin_headers: dict[str, str],
    location_id: int,
) -> None:
    res = client.post(
        "/api/v1/devices",
        json={"name": "room-2", "kind": "ambient", "location_id": location_id},
        headers=admin_headers,
    )
    other_headers = {"Authorization": f"Bearer {res.json()['token']}"}
    batch = {
        "readings": [{"metric": "temperature_c", "value": 20, "recorded_at": "2026-01-01T12:00Z"}]
    }
    for headers in (device_headers, other_headers):
        assert client.post("/api/v1/readings", json=batch, headers=headers).status_code == 201

    stored = client.get("/api/v1/readings", headers=admin_headers).json()
    assert len({r["device_id"] for r in stored}) == 2


def test_backlog_accepted_and_ordered_by_recorded_at(
    client: TestClient, device_headers: dict[str, str], admin_headers: dict[str, str]
) -> None:
    now = datetime.now(UTC)
    days_ago = [3, 1, 2, 0]  # arrival order differs from time order
    batch = {
        "readings": [
            {
                "metric": "temperature_c",
                "value": 20,
                "recorded_at": (now - timedelta(days=d, minutes=1)).isoformat(),
            }
            for d in days_ago
        ]
    }
    res = client.post("/api/v1/readings", json=batch, headers=device_headers)
    assert res.status_code == 201

    stored = client.get("/api/v1/readings", headers=admin_headers).json()
    times = [datetime.fromisoformat(r["recorded_at"]) for r in stored]
    assert len(times) == 4
    assert times == sorted(times, reverse=True)


def test_readings_without_recorded_at_are_never_deduplicated(
    client: TestClient, device_headers: dict[str, str], admin_headers: dict[str, str]
) -> None:
    batch = {"readings": [{"metric": "humidity_pct", "value": 60}] * 2}
    for expected in (2, 4):
        res = client.post("/api/v1/readings", json=batch, headers=device_headers)
        assert res.status_code == 201
        assert res.json() == {"accepted": 2}
        assert len(client.get("/api/v1/readings", headers=admin_headers).json()) == expected


@pytest.mark.parametrize(
    ("headers_fixture", "readings"),
    [
        (
            "device_headers",
            [
                {"metric": "temperature_c", "value": 19.4},
                {"metric": "humidity_pct", "value": 58.2},
                {"metric": "pressure_hpa", "value": 1013.2},
                {"metric": "battery_v", "value": 3.9},
            ],
        ),
        (
            "in_vessel_headers",
            [
                {"metric": "temperature_c", "value": 19.4},
                {"metric": "specific_gravity", "value": 1.050},
                {"metric": "battery_v", "value": 3.9},
            ],
        ),
    ],
)
def test_accepts_every_metric_its_kind_allows(
    request: pytest.FixtureRequest,
    client: TestClient,
    admin_headers: dict[str, str],
    headers_fixture: str,
    readings: list[dict[str, object]],
) -> None:
    headers: dict[str, str] = request.getfixturevalue(headers_fixture)
    res = client.post("/api/v1/readings", json={"readings": readings}, headers=headers)
    assert res.status_code == 201
    assert res.json() == {"accepted": len(readings)}
    assert len(client.get("/api/v1/readings", headers=admin_headers).json()) == len(readings)


@pytest.mark.parametrize(
    ("headers_fixture", "metric", "value"),
    [
        ("device_headers", "specific_gravity", 1.050),
        ("in_vessel_headers", "humidity_pct", 58.2),
        ("in_vessel_headers", "pressure_hpa", 1013.2),
    ],
)
def test_rejects_metric_not_allowed_for_kind(
    request: pytest.FixtureRequest,
    client: TestClient,
    admin_headers: dict[str, str],
    headers_fixture: str,
    metric: str,
    value: float,
) -> None:
    headers: dict[str, str] = request.getfixturevalue(headers_fixture)
    batch = {
        "readings": [
            {"metric": "temperature_c", "value": 19.4},
            {"metric": metric, "value": value},
        ]
    }
    res = client.post("/api/v1/readings", json=batch, headers=headers)
    assert res.status_code == 422
    assert client.get("/api/v1/readings", headers=admin_headers).json() == []
