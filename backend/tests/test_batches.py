from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient

from tests.conftest import post_readings

MakeDevice = Callable[[str], tuple[int, dict[str, str]]]
MakeBatch = Callable[..., int]

JAN_1 = datetime(2026, 1, 1, tzinfo=UTC)
JAN_5 = datetime(2026, 1, 5, tzinfo=UTC)
JAN_10 = datetime(2026, 1, 10, tzinfo=UTC)
JAN_12 = datetime(2026, 1, 12, tzinfo=UTC)
JAN_15 = datetime(2026, 1, 15, tzinfo=UTC)
JAN_20 = datetime(2026, 1, 20, tzinfo=UTC)
JAN_21 = datetime(2026, 1, 21, tzinfo=UTC)


def _create(
    client: TestClient,
    headers: dict[str, str],
    device_id: int,
    started_at: datetime | None = None,
    ended_at: datetime | None = None,
    name: str = "ipa",
) -> int:
    body: dict[str, object] = {"name": name, "device_id": device_id}
    if started_at is not None:
        body["started_at"] = started_at.isoformat()
    if ended_at is not None:
        body["ended_at"] = ended_at.isoformat()
    return client.post("/api/v1/batches", json=body, headers=headers).status_code


def test_create_and_list(
    client: TestClient,
    user_headers: dict[str, str],
    make_device: MakeDevice,
) -> None:
    device_id, _ = make_device("vessel-a")
    res = client.post(
        "/api/v1/batches", json={"name": " ipa ", "device_id": device_id}, headers=user_headers
    )
    assert res.status_code == 201
    created = res.json()
    assert created["name"] == "ipa"
    assert created["device_id"] == device_id
    assert created["ended_at"] is None
    started = datetime.fromisoformat(created["started_at"])
    assert abs(datetime.now(UTC) - started) < timedelta(seconds=30)

    for name, day in (("stout", JAN_1), ("lager", JAN_10)):
        other_id, _ = make_device(f"vessel-{name}")
        assert _create(client, user_headers, other_id, day, name=name) == 201

    listed = client.get("/api/v1/batches", headers=user_headers).json()
    assert [b["name"] for b in listed] == ["ipa", "lager", "stout"]
    one = client.get("/api/v1/batches", params={"limit": 1}, headers=user_headers).json()
    assert [b["name"] for b in one] == ["ipa"]


def test_create_rejects_bad_payloads(
    client: TestClient, user_headers: dict[str, str], make_device: MakeDevice
) -> None:
    device_id, _ = make_device("vessel-a")
    future = (datetime.now(UTC) + timedelta(hours=1)).isoformat()
    ok = {"name": "ipa", "device_id": device_id}
    bad_bodies: list[dict[str, object]] = [
        {**ok, "name": ""},
        {**ok, "name": "   "},
        {**ok, "name": "x" * 65},
        {"name": "ipa"},
        {**ok, "device_id": device_id + 1000},
        {**ok, "started_at": "2026-01-01T12:00:00"},
        {**ok, "started_at": future},
        {**ok, "started_at": "0001-01-01T00:00:00+05:00"},  # out of Postgres's timestamptz range
        {**ok, "started_at": JAN_10.isoformat(), "ended_at": JAN_1.isoformat()},
        {**ok, "started_at": JAN_1.isoformat(), "ended_at": future},
        {**ok, "yeast_min_temperature_c": 18},  # half-set range
        {**ok, "yeast_max_temperature_c": 22},
        {**ok, "yeast_min_temperature_c": 23, "yeast_max_temperature_c": 18},
        {**ok, "yeast_min_temperature_c": -40.1, "yeast_max_temperature_c": 22},  # sensor range
        {**ok, "yeast_min_temperature_c": 18, "yeast_max_temperature_c": 125.1},
        {**ok, "yeast_name": ""},
        {**ok, "yeast_name": "   "},
        {**ok, "yeast_name": "x" * 65},
    ]
    for body in bad_bodies:
        res = client.post("/api/v1/batches", json=body, headers=user_headers)
        assert res.status_code == 422, body


def test_overlap_conflicts(
    client: TestClient, user_headers: dict[str, str], make_device: MakeDevice
) -> None:
    device_a, _ = make_device("vessel-a")
    device_b, _ = make_device("vessel-b")
    assert _create(client, user_headers, device_a, JAN_1, JAN_10) == 201

    # (started_at, ended_at, expected status) against the existing [Jan 1, Jan 10) on device A.
    cases = [
        (JAN_5, JAN_15, 409),  # starts inside
        (JAN_5, None, 409),  # starts inside, open
        (JAN_1 - timedelta(days=5), JAN_5, 409),  # starts before, ends inside
        (JAN_1 - timedelta(days=5), None, 409),  # starts before, open
        (JAN_10, JAN_15, 201),  # starts exactly where the other ends
        (JAN_1 - timedelta(days=5), JAN_1, 201),  # ends exactly where the other starts
    ]
    for started_at, ended_at, expected in cases:
        status = _create(client, user_headers, device_a, started_at, ended_at)
        assert status == expected, (started_at, ended_at)

    # The same window on another device is free.
    assert _create(client, user_headers, device_b, JAN_1, JAN_10) == 201

    # An open batch runs to now: it blocks a later create on its device, not on others.
    open_start = JAN_15 + timedelta(days=30)
    assert _create(client, user_headers, device_a, open_start) == 201
    assert _create(client, user_headers, device_a, open_start + timedelta(days=1)) == 409
    assert _create(client, user_headers, device_b, open_start) == 201


def test_end_batch_then_start_next(
    client: TestClient,
    user_headers: dict[str, str],
    make_device: MakeDevice,
    make_batch: MakeBatch,
) -> None:
    device_id, _ = make_device("vessel-a")
    batch_id = make_batch(device_id, JAN_1)
    assert _create(client, user_headers, device_id, JAN_10) == 409  # first one is still open

    res = client.patch(
        f"/api/v1/batches/{batch_id}", json={"ended_at": JAN_10.isoformat()}, headers=user_headers
    )
    assert res.status_code == 200
    assert datetime.fromisoformat(res.json()["ended_at"]) == JAN_10
    assert _create(client, user_headers, device_id, JAN_10) == 201


def test_end_rejects_bad_times(
    client: TestClient,
    user_headers: dict[str, str],
    make_device: MakeDevice,
    make_batch: MakeBatch,
) -> None:
    device_id, _ = make_device("vessel-a")
    batch_id = make_batch(device_id, JAN_5)
    future = datetime.now(UTC) + timedelta(hours=1)
    for ended_at, expected in ((JAN_1, 422), (future, 422), (JAN_5, 200)):  # JAN_5 voids it
        res = client.patch(
            f"/api/v1/batches/{batch_id}",
            json={"ended_at": ended_at.isoformat()},
            headers=user_headers,
        )
        assert res.status_code == expected, ended_at


def test_update_overlap_conflicts(
    client: TestClient,
    user_headers: dict[str, str],
    make_device: MakeDevice,
    make_batch: MakeBatch,
) -> None:
    device_id, _ = make_device("vessel-a")
    first = make_batch(device_id, JAN_1, JAN_5)
    second = make_batch(device_id, JAN_10, JAN_15)

    # Each change would overlap a neighbour.
    cases = [
        (second, {"started_at": JAN_1.isoformat()}),  # extend back into the previous batch
        (first, {"ended_at": JAN_15.isoformat()}),  # extend forward into the next batch
        (first, {"ended_at": None}),  # reopen while a later batch exists
    ]
    for batch_id, changes in cases:
        res = client.patch(f"/api/v1/batches/{batch_id}", json=changes, headers=user_headers)
        assert res.status_code == 409, changes


def test_update_rejects_nulls_and_unknown_id(
    client: TestClient,
    user_headers: dict[str, str],
    make_device: MakeDevice,
    make_batch: MakeBatch,
) -> None:
    device_id, _ = make_device("vessel-a")
    batch_id = make_batch(device_id, JAN_1, yeast_min_temperature_c=18, yeast_max_temperature_c=22)
    for changes in (
        {"name": None},
        {"name": ""},
        {"started_at": None},
        {"yeast_min_temperature_c": 23},  # above the stored max
        {"yeast_max_temperature_c": 17},  # below the stored min
        {"yeast_min_temperature_c": None},  # half-set range
        {"yeast_max_temperature_c": 130},
        {"yeast_name": ""},
    ):
        res = client.patch(f"/api/v1/batches/{batch_id}", json=changes, headers=user_headers)
        assert res.status_code == 422, changes
    stored = client.get(f"/api/v1/batches/{batch_id}", headers=user_headers).json()
    assert (stored["yeast_min_temperature_c"], stored["yeast_max_temperature_c"]) == (18, 22)

    res = client.patch("/api/v1/batches/999", json={"name": "x"}, headers=user_headers)
    assert res.status_code == 404


def test_yeast_range_round_trips(
    client: TestClient,
    user_headers: dict[str, str],
    make_device: MakeDevice,
    make_batch: MakeBatch,
) -> None:
    device_id, _ = make_device("vessel-a")
    yeast_fields = ("yeast_name", "yeast_min_temperature_c", "yeast_max_temperature_c")

    def yeast(body: dict[str, Any]) -> tuple[object, ...]:
        return tuple(body[field] for field in yeast_fields)

    res = client.post(
        "/api/v1/batches",
        json={
            "name": "ipa",
            "device_id": device_id,
            "started_at": JAN_1.isoformat(),
            "ended_at": JAN_5.isoformat(),
            "yeast_name": " US-05 ",
            "yeast_min_temperature_c": 18,
            "yeast_max_temperature_c": 22,
        },
        headers=user_headers,
    )
    assert res.status_code == 201
    batch_id = res.json()["id"]
    assert yeast(res.json()) == ("US-05", 18, 22)
    url = f"/api/v1/batches/{batch_id}"
    assert yeast(client.get(url, headers=user_headers).json()) == ("US-05", 18, 22)

    res = client.patch(url, json={"yeast_max_temperature_c": 24}, headers=user_headers)
    assert (res.status_code, yeast(res.json())) == (200, ("US-05", 18, 24))

    cleared = dict.fromkeys(yeast_fields)
    assert client.patch(url, json=cleared, headers=user_headers).status_code == 200
    assert yeast(client.get(url, headers=user_headers).json()) == (None, None, None)

    plain = make_batch(device_id, JAN_5, JAN_10)
    assert yeast(client.get(f"/api/v1/batches/{plain}", headers=user_headers).json()) == (
        None,
        None,
        None,
    )
    # The sensor's limits are valid bounds, and a single-temperature range is valid.
    for low, high in ((-40, 125), (20, 20)):
        res = client.patch(
            url,
            json={"yeast_min_temperature_c": low, "yeast_max_temperature_c": high},
            headers=user_headers,
        )
        assert (res.status_code, yeast(res.json())[1:]) == (200, (low, high))


def _get(client: TestClient, headers: dict[str, str], batch_id: int) -> dict[str, Any]:
    res = client.get(f"/api/v1/batches/{batch_id}", headers=headers)
    assert res.status_code == 200
    body: dict[str, Any] = res.json()
    return body


def test_summary_covers_only_the_batch_window(
    client: TestClient,
    user_headers: dict[str, str],
    make_device: MakeDevice,
    make_batch: MakeBatch,
) -> None:
    a_id, a_headers = make_device("vessel-a")
    _, b_headers = make_device("vessel-b")
    post_readings(
        client,
        a_headers,
        [
            ("temperature_c", 5, JAN_5),  # before the window
            ("temperature_c", 18, JAN_10),  # start is inclusive
            ("temperature_c", 20, JAN_12),
            ("temperature_c", 22, JAN_15),
            ("temperature_c", 99, JAN_20),  # shared boundary: belongs to the second batch
            ("temperature_c", 4, JAN_21),
            ("specific_gravity", 1.050, JAN_12),
            ("specific_gravity", 1.020, JAN_15),
        ],
    )
    post_readings(client, b_headers, [("temperature_c", 50, JAN_15)])  # another device
    first = make_batch(a_id, JAN_10, JAN_20)
    second = make_batch(a_id, JAN_20)

    one = _get(client, user_headers, first)
    assert {k: one[k] for k in ("id", "name", "device_id", "ended_at")} == {
        "id": first,
        "name": "ipa",
        "device_id": a_id,
        "ended_at": JAN_20.isoformat().replace("+00:00", "Z"),
    }
    assert datetime.fromisoformat(str(one["started_at"])) == JAN_10
    assert [
        (m["metric"], m["count"], m["min_value"], m["max_value"], m["latest_value"])
        for m in one["metrics"]
    ] == [
        ("specific_gravity", 2, 1.02, 1.05, 1.02),
        ("temperature_c", 3, 18, 22, 22),
    ]
    sg, temp = one["metrics"]
    assert sg["avg_value"] == pytest.approx(1.035)
    assert temp["avg_value"] == pytest.approx(20)
    assert datetime.fromisoformat(temp["latest_recorded_at"]) == JAN_15

    (only,) = _get(client, user_headers, second)["metrics"]
    assert (only["metric"], only["count"], only["min_value"], only["max_value"]) == (
        "temperature_c",
        2,
        4,
        99,
    )
    assert only["avg_value"] == pytest.approx(51.5)
    assert only["latest_value"] == 4
    assert datetime.fromisoformat(only["latest_recorded_at"]) == JAN_21


@pytest.mark.parametrize(
    ("readings", "started_at", "ended_at"),
    [
        pytest.param([], JAN_10, JAN_15, id="no-readings"),
        pytest.param(
            [("temperature_c", 18, JAN_5), ("temperature_c", 19, JAN_15)],
            JAN_10,
            JAN_15,
            id="before-start-and-at-end",
        ),
        pytest.param([("temperature_c", 18, JAN_10)], JAN_10, JAN_10, id="zero-length"),
    ],
)
def test_summary_of_a_batch_without_readings_is_empty(
    client: TestClient,
    user_headers: dict[str, str],
    make_device: MakeDevice,
    make_batch: MakeBatch,
    readings: list[tuple[str, float, datetime | None]],
    started_at: datetime,
    ended_at: datetime,
) -> None:
    device_id, headers = make_device("vessel-a")
    if readings:
        post_readings(client, headers, readings)
    batch_id = make_batch(device_id, started_at, ended_at)
    assert _get(client, user_headers, batch_id)["metrics"] == []


def test_summary_of_a_single_reading(
    client: TestClient,
    user_headers: dict[str, str],
    make_device: MakeDevice,
    make_batch: MakeBatch,
) -> None:
    device_id, headers = make_device("vessel-a")
    post_readings(client, headers, [("specific_gravity", 1.04, JAN_10)])
    batch_id = make_batch(device_id, JAN_5, JAN_15)

    (summary,) = _get(client, user_headers, batch_id)["metrics"]
    assert summary["count"] == 1
    assert (
        summary["min_value"]
        == summary["max_value"]
        == summary["avg_value"]
        == summary["latest_value"]
        == 1.04
    )
    assert datetime.fromisoformat(summary["latest_recorded_at"]) == JAN_10


def test_open_batch_summary_runs_to_now(
    client: TestClient,
    user_headers: dict[str, str],
    make_device: MakeDevice,
    make_batch: MakeBatch,
) -> None:
    device_id, headers = make_device("vessel-a")
    batch_id = make_batch(device_id, JAN_1)
    ahead = datetime.now(UTC) + timedelta(minutes=3)  # device clock skew, still accepted
    # Clockless readings share one server-stamped recorded_at: the later insert is "latest".
    post_readings(
        client,
        headers,
        [("temperature_c", 10, None), ("temperature_c", 20, None), ("temperature_c", 99, ahead)],
    )

    (summary,) = _get(client, user_headers, batch_id)["metrics"]
    assert summary["count"] == 2
    assert summary["latest_value"] == 20
    assert summary["max_value"] == 20  # the reading ahead of now is excluded, as in list_readings


def test_yeast_fit_times_readings_against_the_range(
    client: TestClient,
    user_headers: dict[str, str],
    make_device: MakeDevice,
    make_batch: MakeBatch,
) -> None:
    a_id, a_headers = make_device("vessel-a")
    _, b_headers = make_device("vessel-b")
    # 10 min apart, each spanning until the next; 18 and 22 sit on the bounds, the last 20 is the
    # newest and counts zero.
    in_window = [
        ("temperature_c", value, JAN_10 + timedelta(minutes=10 * i))
        for i, value in enumerate((17.9, 18, 20, 22, 22.1, 20))
    ]
    post_readings(
        client,
        a_headers,
        [
            *in_window,
            ("temperature_c", 30, JAN_5),  # before the window
            ("temperature_c", 30, JAN_20),  # at ended_at: outside, so never the newest's neighbour
            ("specific_gravity", 1.05, JAN_12),  # not a temperature
        ],
    )
    post_readings(client, b_headers, [("temperature_c", 30, JAN_12)])  # another device
    batch_id = make_batch(
        a_id, JAN_10, JAN_20, yeast_min_temperature_c=18, yeast_max_temperature_c=22
    )
    assert _get(client, user_headers, batch_id)["yeast_fit"] == {
        "below_s": 600,
        "inside_s": 1800,
        "above_s": 600,
    }

    res = client.patch(
        f"/api/v1/batches/{batch_id}",
        json={"yeast_min_temperature_c": 10, "yeast_max_temperature_c": 15},
        headers=user_headers,
    )
    assert res.status_code == 200
    assert _get(client, user_headers, batch_id)["yeast_fit"] == {
        "below_s": 0,
        "inside_s": 0,
        "above_s": 3000,
    }


T = JAN_12
MIN = timedelta(minutes=1)
RANGE_18_22 = {"yeast_min_temperature_c": 18, "yeast_max_temperature_c": 22}


def _fit(below_s: int = 0, inside_s: int = 0, above_s: int = 0) -> dict[str, int]:
    return {"below_s": below_s, "inside_s": inside_s, "above_s": above_s}


@pytest.mark.parametrize(
    ("readings", "yeast_range", "ended_at", "expected"),
    [
        pytest.param([("temperature_c", 20, T)], {}, JAN_20, None, id="no-range"),
        pytest.param(
            [("specific_gravity", 1.05, T)], RANGE_18_22, JAN_20, _fit(), id="range-no-temperature"
        ),
        pytest.param([], RANGE_18_22, JAN_20, _fit(), id="range-no-readings"),
        pytest.param([("temperature_c", 25, T)], RANGE_18_22, JAN_20, _fit(), id="one-reading"),
        pytest.param(
            [
                ("temperature_c", 20, T),
                ("temperature_c", 21, T + 30 * MIN),
                ("temperature_c", 19, T + 60 * MIN),
            ],
            RANGE_18_22,
            JAN_20,
            _fit(inside_s=3600),
            id="all-inside",
        ),
        pytest.param(
            [
                ("temperature_c", 18, T),
                ("temperature_c", 22, T + 10 * MIN),
                ("temperature_c", 20, T + 20 * MIN),
            ],
            RANGE_18_22,
            JAN_20,
            _fit(inside_s=1200),
            id="on-bounds",
        ),
        pytest.param(
            [("temperature_c", 25, T), ("temperature_c", 20, T + 5 * 60 * MIN)],
            RANGE_18_22,
            JAN_20,
            _fit(above_s=3600),
            id="long-gap-capped",
        ),
        pytest.param(
            [("temperature_c", 20, T), ("temperature_c", 30, T + 10 * MIN)],
            RANGE_18_22,
            None,
            _fit(inside_s=600),
            id="open-batch-newest-counts-zero",
        ),
    ],
)
def test_yeast_fit_edge_cases(
    client: TestClient,
    user_headers: dict[str, str],
    make_device: MakeDevice,
    make_batch: MakeBatch,
    readings: list[tuple[str, float, datetime | None]],
    yeast_range: dict[str, float],
    ended_at: datetime | None,
    expected: dict[str, int] | None,
) -> None:
    device_id, headers = make_device("vessel-a")
    if readings:
        post_readings(client, headers, readings)
    batch_id = make_batch(device_id, JAN_10, ended_at, **yeast_range)
    detail = _get(client, user_headers, batch_id)
    assert detail["yeast_fit"] == expected
    assert len(detail["metrics"]) == len({m for m, _, _ in readings})  # the summary is unaffected


def test_get_unknown_batch_is_404(client: TestClient, user_headers: dict[str, str]) -> None:
    assert client.get("/api/v1/batches/999", headers=user_headers).status_code == 404


def test_list_filters_by_device(
    client: TestClient,
    user_headers: dict[str, str],
    other_user_headers: dict[str, str],
    make_device: MakeDevice,
    make_batch: MakeBatch,
) -> None:
    a, _ = make_device("vessel-a")
    b, _ = make_device("vessel-b")
    a_closed = make_batch(a, JAN_1, JAN_5)
    a_open = make_batch(a, JAN_10)
    b_batch = make_batch(b, JAN_12)  # newest overall, so a `limit` before the filter shows
    bob_device = client.post(
        "/api/v1/devices",
        json={"name": "vessel-c", "kind": "in_vessel"},
        headers=other_user_headers,
    ).json()["id"]
    make_batch(bob_device, JAN_1, headers=other_user_headers)

    for headers, params, expected in (
        (user_headers, {"device_id": a}, [a_open, a_closed]),
        (user_headers, {"device_id": b}, [b_batch]),
        (user_headers, {"device_id": a, "limit": 1}, [a_open]),
        (user_headers, {"device_id": bob_device}, []),  # foreign answers like unknown
        (user_headers, {"device_id": 999}, []),
    ):
        res = client.get("/api/v1/batches", params=params, headers=headers)
        assert res.status_code == 200, params
        assert [batch["id"] for batch in res.json()] == expected, params


def test_owners_cannot_see_each_others_batches(
    client: TestClient,
    user_headers: dict[str, str],
    other_user_headers: dict[str, str],
    make_device: MakeDevice,
    make_batch: MakeBatch,
) -> None:
    alice_device, _ = make_device("vessel-a")
    alice_batch = make_batch(alice_device, JAN_10)  # newer than bob's, so it fills `limit=1`
    bob_device = client.post(
        "/api/v1/devices",
        json={"name": "vessel-b", "kind": "in_vessel"},
        headers=other_user_headers,
    ).json()["id"]
    res = client.post(
        "/api/v1/batches",
        json={"name": "stout", "device_id": bob_device, "started_at": JAN_1.isoformat()},
        headers=other_user_headers,
    )
    assert res.status_code == 201
    bob_batch = res.json()["id"]

    def ids(headers: dict[str, str], **params: int) -> list[int]:
        res = client.get("/api/v1/batches", params=params, headers=headers)
        return [b["id"] for b in res.json()]

    assert ids(user_headers) == [alice_batch]
    assert ids(other_user_headers) == [bob_batch]
    assert ids(other_user_headers, limit=1) == [bob_batch]  # the owner filter runs before `limit`
    for headers, batch_id in (
        (user_headers, alice_batch),
        (other_user_headers, bob_batch),
    ):
        assert client.get(f"/api/v1/batches/{batch_id}", headers=headers).status_code == 200

    # A foreign row answers exactly like a missing one: nothing reveals that it exists.
    for method, body in (("GET", None), ("PATCH", {"name": "x"})):
        foreign = client.request(
            method, f"/api/v1/batches/{alice_batch}", json=body, headers=other_user_headers
        )
        missing = client.request(
            method, "/api/v1/batches/999", json=body, headers=other_user_headers
        )
        assert foreign.status_code == 404, method
        assert (foreign.status_code, foreign.json()) == (missing.status_code, missing.json())
    assert (
        client.get(f"/api/v1/batches/{alice_batch}", headers=user_headers).json()["name"] == "ipa"
    )

    new_batch = {"name": "x", "started_at": JAN_1.isoformat()}
    foreign_device = client.post(
        "/api/v1/batches", json={**new_batch, "device_id": alice_device}, headers=other_user_headers
    )
    unknown_device = client.post(
        "/api/v1/batches", json={**new_batch, "device_id": 999}, headers=other_user_headers
    )
    assert foreign_device.status_code == 422
    assert (foreign_device.status_code, foreign_device.json()) == (
        unknown_device.status_code,
        unknown_device.json(),
    )
    assert ids(user_headers) == [alice_batch]

    res = client.patch(
        f"/api/v1/batches/{alice_batch}", json={"name": "pale"}, headers=user_headers
    )
    assert (res.status_code, res.json()["name"]) == (200, "pale")
