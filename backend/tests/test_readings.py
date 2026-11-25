from collections.abc import Callable
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from tests.conftest import post_readings


def test_ingest_and_list(
    client: TestClient, device_headers: dict[str, str], user_headers: dict[str, str]
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
        "/api/v1/readings", params={"metric": "temperature_c"}, headers=user_headers
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
    client: TestClient, device_headers: dict[str, str], user_headers: dict[str, str]
) -> None:
    def reading(minute: int) -> dict[str, object]:
        return {
            "metric": "temperature_c",
            "value": 18.0 + minute,
            "recorded_at": f"2026-01-01T12:0{minute}:00Z",
        }

    def stored() -> int:
        return len(client.get("/api/v1/readings", headers=user_headers).json())

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
    values = [r["value"] for r in client.get("/api/v1/readings", headers=user_headers).json()]
    assert stored() == 3
    assert 99.0 not in values


def test_same_reading_from_two_devices_is_stored_twice(
    client: TestClient,
    device_headers: dict[str, str],
    user_headers: dict[str, str],
    location_id: int,
) -> None:
    res = client.post(
        "/api/v1/devices",
        json={"name": "room-2", "kind": "ambient", "location_id": location_id},
        headers=user_headers,
    )
    other_headers = {"Authorization": f"Bearer {res.json()['token']}"}
    batch = {
        "readings": [{"metric": "temperature_c", "value": 20, "recorded_at": "2026-01-01T12:00Z"}]
    }
    for headers in (device_headers, other_headers):
        assert client.post("/api/v1/readings", json=batch, headers=headers).status_code == 201

    stored = client.get("/api/v1/readings", headers=user_headers).json()
    assert len({r["device_id"] for r in stored}) == 2


def test_backlog_accepted_and_ordered_by_recorded_at(
    client: TestClient, device_headers: dict[str, str], user_headers: dict[str, str]
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

    stored = client.get("/api/v1/readings", headers=user_headers).json()
    times = [datetime.fromisoformat(r["recorded_at"]) for r in stored]
    assert len(times) == 4
    assert times == sorted(times, reverse=True)


def test_list_readings_since_is_inclusive(
    client: TestClient, device_headers: dict[str, str], user_headers: dict[str, str]
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
        "/api/v1/readings", params={"since": "2026-01-01T12:00:00+00:00"}, headers=user_headers
    )
    assert res.status_code == 200
    assert [r["value"] for r in res.json()] == [20.0, 19.0]  # 12:01 then 12:00, newest first


def test_readings_without_recorded_at_are_never_deduplicated(
    client: TestClient, device_headers: dict[str, str], user_headers: dict[str, str]
) -> None:
    batch = {"readings": [{"metric": "humidity_pct", "value": 60}] * 2}
    for expected in (2, 4):
        res = client.post("/api/v1/readings", json=batch, headers=device_headers)
        assert res.status_code == 201
        assert res.json() == {"accepted": 2}
        assert len(client.get("/api/v1/readings", headers=user_headers).json()) == expected


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
    user_headers: dict[str, str],
    headers_fixture: str,
    readings: list[dict[str, object]],
) -> None:
    headers: dict[str, str] = request.getfixturevalue(headers_fixture)
    res = client.post("/api/v1/readings", json={"readings": readings}, headers=headers)
    assert res.status_code == 201
    assert res.json() == {"accepted": len(readings)}
    assert len(client.get("/api/v1/readings", headers=user_headers).json()) == len(readings)


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
    user_headers: dict[str, str],
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
    assert client.get("/api/v1/readings", headers=user_headers).json() == []


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
    user_headers: dict[str, str],
    metric: str,
    headers_fixture: str,
    low: float,
    high: float,
    below: float,
    above: float,
) -> None:
    headers: dict[str, str] = request.getfixturevalue(headers_fixture)

    def stored() -> int:
        return len(client.get("/api/v1/readings", headers=user_headers).json())

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


def _days(client: TestClient, headers: dict[str, str], **params: str | int) -> list[int]:
    res = client.get("/api/v1/readings", params=params, headers=headers)
    assert res.status_code == 200
    return [datetime.fromisoformat(r["recorded_at"]).day for r in res.json()]


def test_batch_filter_returns_only_its_window(
    client: TestClient,
    user_headers: dict[str, str],
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
    assert _days(client, user_headers, batch_id=first) == [15, 10]
    # The reading on the shared boundary belongs to exactly one batch.
    assert _days(client, user_headers, batch_id=second) == [21, 20]

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
    assert _days(client, user_headers, batch_id=second) == [21, 20]


def test_batch_filter_composes_with_other_params(
    client: TestClient,
    user_headers: dict[str, str],
    make_device: MakeDevice,
    make_batch: MakeBatch,
) -> None:
    a_id, a_headers = make_device("vessel-a")
    b_id, _ = make_device("vessel-b")
    _ingest(client, a_headers, "temperature_c", [11, 12, 15])
    _ingest(client, a_headers, "specific_gravity", [13])
    batch = make_batch(a_id, _dt(10), _dt(20))

    assert _days(client, user_headers, batch_id=batch) == [15, 13, 12, 11]
    assert _days(client, user_headers, batch_id=batch, metric="temperature_c") == [15, 12, 11]
    assert _days(client, user_headers, batch_id=batch, since=_day(12)) == [15, 13, 12]
    assert _days(client, user_headers, batch_id=batch, limit=1) == [15]
    assert _days(client, user_headers, batch_id=batch, device_id=a_id) == [15, 13, 12, 11]
    assert _days(client, user_headers, batch_id=batch, device_id=b_id) == []


# Both routes that take a batch_id; the buckets route also needs its own required params.
BATCH_ROUTES = pytest.mark.parametrize(
    ("path", "extra"),
    [
        ("/api/v1/readings", {}),
        # 1d: the batch below is open since 2026-01-10, too long for a finer bucket's cap.
        ("/api/v1/readings/buckets", {"metric": "temperature_c", "bucket": "1d"}),
    ],
)


@BATCH_ROUTES
def test_unknown_batch_id_is_404(
    client: TestClient, user_headers: dict[str, str], path: str, extra: dict[str, str]
) -> None:
    res = client.get(path, params={"batch_id": 999, **extra}, headers=user_headers)
    assert res.status_code == 404


def test_user_sees_only_readings_of_their_devices(
    client: TestClient,
    user_headers: dict[str, str],
    other_user_headers: dict[str, str],
    make_device: MakeDevice,
) -> None:
    alice_id, alice_token = make_device("alice-live")
    revoked_id, revoked_token = make_device("alice-revoked")
    bob = client.post(
        "/api/v1/devices", json={"name": "bob", "kind": "in_vessel"}, headers=other_user_headers
    ).json()
    bob_id, bob_token = bob["id"], {"Authorization": f"Bearer {bob['token']}"}
    for token, days in [(alice_token, [1]), (revoked_token, [2]), (bob_token, [3])]:
        _ingest(client, token, "temperature_c", days)
    client.post(f"/api/v1/devices/{revoked_id}/revoke", headers=user_headers)

    # A revoked device's readings stay with its owner: the scope joins on the device, not its token.
    assert _days(client, user_headers) == [2, 1]
    assert _days(client, other_user_headers) == [3]

    # Another owner's device id is indistinguishable from an unknown one.
    assert _days(client, user_headers, device_id=bob_id) == []
    assert _days(client, user_headers, device_id=999) == []
    assert _days(client, user_headers, device_id=alice_id) == [1]


@BATCH_ROUTES
def test_foreign_batch_id_is_404(
    client: TestClient,
    user_headers: dict[str, str],
    other_user_headers: dict[str, str],
    make_device: MakeDevice,
    make_batch: MakeBatch,
    path: str,
    extra: dict[str, str],
) -> None:
    device_id, token = make_device("alice-vessel")
    _ingest(client, token, "temperature_c", [15])
    batch = make_batch(device_id, _dt(10))

    foreign = client.get(path, params={"batch_id": batch, **extra}, headers=other_user_headers)
    missing = client.get(path, params={"batch_id": 999, **extra}, headers=other_user_headers)
    assert foreign.status_code == 404
    assert (foreign.status_code, foreign.json()) == (missing.status_code, missing.json())

    owner = client.get(path, params={"batch_id": batch, **extra}, headers=user_headers)
    assert owner.status_code == 200
    assert len(owner.json()) == 1


def _at(hhmm: str) -> datetime:
    return datetime.fromisoformat(f"2026-01-10T{hhmm}:00+00:00")


def _buckets(
    client: TestClient, headers: dict[str, str], **params: str | int
) -> list[tuple[datetime, float, float, float]]:
    res = client.get("/api/v1/readings/buckets", params=params, headers=headers)
    assert res.status_code == 200, res.json()
    return [
        (
            datetime.fromisoformat(b["bucket_start"]),
            b["avg_value"],
            b["min_value"],
            b["max_value"],
        )
        for b in res.json()
    ]


@pytest.fixture
def bucketed_batch(
    client: TestClient, make_device: MakeDevice, make_batch: MakeBatch
) -> tuple[int, int]:
    """A batch on device A from 10:05 to 12:00 on 2026-01-10, with readings in and around it.

    Returns the batch id and device A's id.
    """
    a_id, a_headers = make_device("vessel-a")
    _, b_headers = make_device("vessel-b")
    post_readings(
        client,
        a_headers,
        [
            ("temperature_c", 99.0, _at("10:00")),  # before the batch starts
            ("temperature_c", 10.0, _at("10:10")),
            ("temperature_c", 14.0, _at("10:50")),
            ("temperature_c", 12.0, _at("11:20")),
            ("specific_gravity", 1.05, _at("10:30")),
        ],
    )
    post_readings(client, b_headers, [("temperature_c", 50.0, _at("10:30"))])
    return make_batch(a_id, _at("10:05"), _at("12:00")), a_id


def test_buckets_aggregate_per_clock_aligned_bucket(
    client: TestClient, user_headers: dict[str, str], bucketed_batch: tuple[int, int]
) -> None:
    batch, _ = bucketed_batch
    # The first bucket starts at 10:00, before the batch, yet holds only in-window readings.
    assert _buckets(client, user_headers, batch_id=batch, metric="temperature_c", bucket="1h") == [
        (_at("10:00"), 12.0, 10.0, 14.0),
        (_at("11:00"), 12.0, 12.0, 12.0),
    ]


def test_buckets_since_and_empty_window(
    client: TestClient,
    user_headers: dict[str, str],
    bucketed_batch: tuple[int, int],
    make_batch: MakeBatch,
) -> None:
    batch, device_id = bucketed_batch
    params = {"metric": "temperature_c", "bucket": "1h"}
    since_11 = _buckets(
        client, user_headers, batch_id=batch, since=_at("11:00").isoformat(), **params
    )
    assert since_11 == [(_at("11:00"), 12.0, 12.0, 12.0)]
    after_end = _buckets(
        client, user_headers, batch_id=batch, since=_at("12:30").isoformat(), **params
    )
    assert after_end == []

    empty = make_batch(device_id, _at("13:00"), _at("14:00"))  # no reading in its window
    assert _buckets(client, user_headers, batch_id=empty, **params) == []


def test_buckets_rejects_bad_requests(
    client: TestClient,
    user_headers: dict[str, str],
    make_device: MakeDevice,
    make_batch: MakeBatch,
) -> None:
    device_id, _ = make_device("vessel-a")
    end = _dt(31)
    batch = make_batch(device_id, _dt(1), end)
    fits = end - 4999 * timedelta(minutes=5)  # exactly MAX_BUCKETS 5-minute buckets
    base: dict[str, str | int] = {"batch_id": batch, "metric": "temperature_c", "bucket": "15m"}
    cases: list[tuple[dict[str, str | int], int]] = [
        ({**base, "bucket": "2m"}, 422),
        ({k: v for k, v in base.items() if k != "bucket"}, 422),
        ({k: v for k, v in base.items() if k != "metric"}, 422),
        ({k: v for k, v in base.items() if k != "batch_id"}, 422),
        ({**base, "since": "2026-01-10T00:00:00"}, 422),  # naive
        ({**base, "bucket": "5m"}, 422),  # whole window: 8641 buckets
        (base, 200),
        ({**base, "bucket": "5m", "since": fits.isoformat()}, 200),
        ({**base, "bucket": "5m", "since": (fits - timedelta(seconds=1)).isoformat()}, 422),
    ]
    for params, expected in cases:
        res = client.get("/api/v1/readings/buckets", params=params, headers=user_headers)
        assert res.status_code == expected, params
