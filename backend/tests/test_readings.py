from collections.abc import Callable
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

    # same key, different value: first write wins, still 201
    conflicting = {"readings": [{**reading(1), "value": 99.0}]}
    res = client.post("/api/v1/readings", json=conflicting, headers=device_headers)
    assert res.status_code == 201
    assert res.json() == {"accepted": 1}
    values = [r["value"] for r in client.get("/api/v1/readings", headers=admin_headers).json()]
    assert stored() == 3
    assert 99.0 not in values


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


def test_list_readings_since_is_inclusive(
    client: TestClient, device_headers: dict[str, str], admin_headers: dict[str, str]
) -> None:
    batch = {
        "readings": [
            {"metric": "temperature_c", "value": 18.0 + minute, "recorded_at": ts}
            for minute, ts in enumerate(
                ["2026-01-01T11:59:00Z", "2026-01-01T12:00:00Z", "2026-01-01T12:01:00Z"]
            )
        ]
    }
    assert client.post("/api/v1/readings", json=batch, headers=device_headers).status_code == 201

    res = client.get(
        "/api/v1/readings", params={"since": "2026-01-01T12:00:00+00:00"}, headers=admin_headers
    )
    assert res.status_code == 200
    assert [r["value"] for r in res.json()] == [20.0, 19.0]  # 12:01 then 12:00, newest first


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


@pytest.mark.parametrize(
    ("metric", "headers_fixture", "low", "high", "below", "above"),
    [
        ("temperature_c", "device_headers", -40, 125, -40.1, 125.1),
        ("humidity_pct", "device_headers", 0, 100, -0.1, 100.1),
        ("pressure_hpa", "device_headers", 300, 1100, 299.9, 1100.1),
        ("specific_gravity", "in_vessel_headers", 0.980, 1.200, 0.979, 1.201),
        ("battery_v", "in_vessel_headers", 0, 5.5, -0.1, 5.6),
    ],
)
def test_value_bounds_per_metric(
    request: pytest.FixtureRequest,
    client: TestClient,
    admin_headers: dict[str, str],
    metric: str,
    headers_fixture: str,
    low: float,
    high: float,
    below: float,
    above: float,
) -> None:
    headers: dict[str, str] = request.getfixturevalue(headers_fixture)

    def stored() -> int:
        return len(client.get("/api/v1/readings", headers=admin_headers).json())

    # Both edges are inclusive.
    edges = {"readings": [{"metric": metric, "value": low}, {"metric": metric, "value": high}]}
    assert client.post("/api/v1/readings", json=edges, headers=headers).status_code == 201
    assert stored() == 2

    # A bad value rejects the whole batch, so the good reading beside it is not stored.
    for bad in (below, above):
        mixed = {"readings": [{"metric": metric, "value": low}, {"metric": metric, "value": bad}]}
        assert client.post("/api/v1/readings", json=mixed, headers=headers).status_code == 422
        assert stored() == 2


MakeDevice = Callable[[str], tuple[int, dict[str, str]]]
MakeBatch = Callable[..., int]


def _dt(day: int) -> datetime:
    return datetime(2026, 1, day, tzinfo=UTC)


def _day(day: int) -> str:
    return _dt(day).isoformat()


def _ingest(client: TestClient, headers: dict[str, str], metric: str, days: list[int]) -> None:
    # Value 1.00x is inside every metric's range.
    readings = [{"metric": metric, "value": 1.0 + d / 1000, "recorded_at": _day(d)} for d in days]
    res = client.post("/api/v1/readings", json={"readings": readings}, headers=headers)
    assert res.status_code == 201


def _days(client: TestClient, admin_headers: dict[str, str], **params: str | int) -> list[int]:
    res = client.get("/api/v1/readings", params=params, headers=admin_headers)
    assert res.status_code == 200
    return [datetime.fromisoformat(r["recorded_at"]).day for r in res.json()]


def test_batch_filter_returns_only_its_window(
    client: TestClient,
    admin_headers: dict[str, str],
    make_device: MakeDevice,
    make_batch: MakeBatch,
) -> None:
    a_id, a_headers = make_device("vessel-a")
    _, b_headers = make_device("vessel-b")
    _ingest(client, a_headers, "temperature_c", [9, 10, 15, 20, 21])
    _ingest(client, b_headers, "temperature_c", [15])
    first = make_batch(a_id, _dt(10), _dt(20))
    second = make_batch(a_id, _dt(20))  # open, starts where the first ends

    # Start inclusive, end exclusive, other devices excluded.
    assert _days(client, admin_headers, batch_id=first) == [15, 10]
    # The reading on the shared boundary belongs to exactly one batch.
    assert _days(client, admin_headers, batch_id=second) == [21, 20]

    # An open batch runs "to now": a reading a few minutes ahead (device clock skew) stays out.
    ahead = datetime.now(UTC) + timedelta(minutes=3)
    res = client.post(
        "/api/v1/readings",
        json={
            "readings": [{"metric": "temperature_c", "value": 20, "recorded_at": ahead.isoformat()}]
        },
        headers=a_headers,
    )
    assert res.status_code == 201
    assert _days(client, admin_headers, batch_id=second) == [21, 20]


def test_batch_filter_composes_with_other_params(
    client: TestClient,
    admin_headers: dict[str, str],
    make_device: MakeDevice,
    make_batch: MakeBatch,
) -> None:
    a_id, a_headers = make_device("vessel-a")
    b_id, _ = make_device("vessel-b")
    _ingest(client, a_headers, "temperature_c", [11, 12, 15])
    _ingest(client, a_headers, "specific_gravity", [13])
    batch = make_batch(a_id, _dt(10), _dt(20))

    assert _days(client, admin_headers, batch_id=batch) == [15, 13, 12, 11]
    assert _days(client, admin_headers, batch_id=batch, metric="temperature_c") == [15, 12, 11]
    assert _days(client, admin_headers, batch_id=batch, since=_day(12)) == [15, 13, 12]
    assert _days(client, admin_headers, batch_id=batch, limit=1) == [15]
    assert _days(client, admin_headers, batch_id=batch, device_id=a_id) == [15, 13, 12, 11]
    assert _days(client, admin_headers, batch_id=batch, device_id=b_id) == []


def test_unknown_batch_id_is_404(client: TestClient, admin_headers: dict[str, str]) -> None:
    res = client.get("/api/v1/readings", params={"batch_id": 999}, headers=admin_headers)
    assert res.status_code == 404
