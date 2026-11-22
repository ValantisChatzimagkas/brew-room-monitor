from collections.abc import Callable
from datetime import UTC, datetime, timedelta
from typing import Any

import pytest
from fastapi.testclient import TestClient

MakeDevice = Callable[[str], tuple[int, dict[str, str]]]
MakeBatch = Callable[..., int]

JAN_1 = datetime(2026, 1, 1, tzinfo=UTC)
JAN_5 = datetime(2026, 1, 5, tzinfo=UTC)
JAN_10 = datetime(2026, 1, 10, tzinfo=UTC)
JAN_15 = datetime(2026, 1, 15, tzinfo=UTC)
JAN_20 = datetime(2026, 1, 20, tzinfo=UTC)
JAN_21 = datetime(2026, 1, 21, tzinfo=UTC)


def _create(
    client: TestClient,
    admin_headers: dict[str, str],
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
    return client.post("/api/v1/batches", json=body, headers=admin_headers).status_code


def test_create_and_list(
    client: TestClient, admin_headers: dict[str, str], make_device: MakeDevice
) -> None:
    device_id, _ = make_device("vessel-a")
    res = client.post(
        "/api/v1/batches", json={"name": " ipa ", "device_id": device_id}, headers=admin_headers
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
        assert _create(client, admin_headers, other_id, day, name=name) == 201

    listed = client.get("/api/v1/batches", headers=admin_headers).json()
    assert [b["name"] for b in listed] == ["ipa", "lager", "stout"]
    one = client.get("/api/v1/batches", params={"limit": 1}, headers=admin_headers).json()
    assert [b["name"] for b in one] == ["ipa"]


def test_create_rejects_bad_payloads(
    client: TestClient, admin_headers: dict[str, str], make_device: MakeDevice
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
    ]
    for body in bad_bodies:
        res = client.post("/api/v1/batches", json=body, headers=admin_headers)
        assert res.status_code == 422, body


def test_overlap_conflicts(
    client: TestClient, admin_headers: dict[str, str], make_device: MakeDevice
) -> None:
    device_a, _ = make_device("vessel-a")
    device_b, _ = make_device("vessel-b")
    assert _create(client, admin_headers, device_a, JAN_1, JAN_10) == 201

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
        status = _create(client, admin_headers, device_a, started_at, ended_at)
        assert status == expected, (started_at, ended_at)

    # The same window on another device is free.
    assert _create(client, admin_headers, device_b, JAN_1, JAN_10) == 201

    # An open batch runs to now: it blocks a later create on its device, not on others.
    open_start = JAN_15 + timedelta(days=30)
    assert _create(client, admin_headers, device_a, open_start) == 201
    assert _create(client, admin_headers, device_a, open_start + timedelta(days=1)) == 409
    assert _create(client, admin_headers, device_b, open_start) == 201


def test_end_batch_then_start_next(
    client: TestClient,
    admin_headers: dict[str, str],
    make_device: MakeDevice,
    make_batch: MakeBatch,
) -> None:
    device_id, _ = make_device("vessel-a")
    batch_id = make_batch(device_id, JAN_1)
    assert _create(client, admin_headers, device_id, JAN_10) == 409  # first one is still open

    res = client.patch(
        f"/api/v1/batches/{batch_id}", json={"ended_at": JAN_10.isoformat()}, headers=admin_headers
    )
    assert res.status_code == 200
    assert datetime.fromisoformat(res.json()["ended_at"]) == JAN_10
    assert _create(client, admin_headers, device_id, JAN_10) == 201


def test_end_rejects_bad_times(
    client: TestClient,
    admin_headers: dict[str, str],
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
            headers=admin_headers,
        )
        assert res.status_code == expected, ended_at


def test_update_overlap_conflicts(
    client: TestClient,
    admin_headers: dict[str, str],
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
        res = client.patch(f"/api/v1/batches/{batch_id}", json=changes, headers=admin_headers)
        assert res.status_code == 409, changes


def test_update_rejects_nulls_and_unknown_id(
    client: TestClient,
    admin_headers: dict[str, str],
    make_device: MakeDevice,
    make_batch: MakeBatch,
) -> None:
    device_id, _ = make_device("vessel-a")
    batch_id = make_batch(device_id, JAN_1)
    for changes in ({"name": None}, {"name": ""}, {"started_at": None}):
        res = client.patch(f"/api/v1/batches/{batch_id}", json=changes, headers=admin_headers)
        assert res.status_code == 422, changes

    res = client.patch("/api/v1/batches/999", json={"name": "x"}, headers=admin_headers)
    assert res.status_code == 404


def _day(d: int) -> datetime:
    return datetime(2026, 1, d, tzinfo=UTC)


def _ingest(
    client: TestClient,
    headers: dict[str, str],
    readings: list[tuple[str, float, datetime | None]],
) -> None:
    body = [
        {"metric": m, "value": v, **({"recorded_at": at.isoformat()} if at else {})}
        for m, v, at in readings
    ]
    res = client.post("/api/v1/readings", json={"readings": body}, headers=headers)
    assert res.status_code == 201


def _get(client: TestClient, admin_headers: dict[str, str], batch_id: int) -> dict[str, Any]:
    res = client.get(f"/api/v1/batches/{batch_id}", headers=admin_headers)
    assert res.status_code == 200
    body: dict[str, Any] = res.json()
    return body


def test_summary_covers_only_the_batch_window(
    client: TestClient,
    admin_headers: dict[str, str],
    make_device: MakeDevice,
    make_batch: MakeBatch,
) -> None:
    a_id, a_headers = make_device("vessel-a")
    _, b_headers = make_device("vessel-b")
    _ingest(
        client,
        a_headers,
        [
            ("temperature_c", 5, _day(9)),  # before the window
            ("temperature_c", 18, _day(10)),  # start is inclusive
            ("temperature_c", 20, _day(12)),
            ("temperature_c", 22, _day(15)),
            ("temperature_c", 99, JAN_20),  # shared boundary: belongs to the second batch
            ("temperature_c", 4, JAN_21),
            ("specific_gravity", 1.050, _day(12)),
            ("specific_gravity", 1.020, _day(15)),
        ],
    )
    _ingest(client, b_headers, [("temperature_c", 50, _day(15))])  # another device
    first = make_batch(a_id, JAN_10, JAN_20)
    second = make_batch(a_id, JAN_20)

    one = _get(client, admin_headers, first)
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
    assert datetime.fromisoformat(temp["latest_recorded_at"]) == _day(15)

    (only,) = _get(client, admin_headers, second)["metrics"]
    assert (only["metric"], only["count"], only["min_value"], only["max_value"]) == (
        "temperature_c",
        2,
        4,
        99,
    )
    assert only["avg_value"] == pytest.approx(51.5)
    assert only["latest_value"] == 4
    assert datetime.fromisoformat(only["latest_recorded_at"]) == JAN_21


def test_summary_of_empty_and_single_reading_batches(
    client: TestClient,
    admin_headers: dict[str, str],
    make_device: MakeDevice,
    make_batch: MakeBatch,
) -> None:
    empty_id, _ = make_device("vessel-empty")
    assert _get(client, admin_headers, make_batch(empty_id, JAN_10, JAN_15))["metrics"] == []

    outside_id, outside_headers = make_device("vessel-outside")
    _ingest(
        client,
        outside_headers,
        [("temperature_c", 18, JAN_5), ("temperature_c", 19, JAN_15)],  # before start, at end
    )
    assert _get(client, admin_headers, make_batch(outside_id, JAN_10, JAN_15))["metrics"] == []

    zero_id, zero_headers = make_device("vessel-zero")
    _ingest(client, zero_headers, [("temperature_c", 18, JAN_10)])
    assert _get(client, admin_headers, make_batch(zero_id, JAN_10, JAN_10))["metrics"] == []

    one_id, one_headers = make_device("vessel-one")
    _ingest(client, one_headers, [("specific_gravity", 1.04, JAN_10)])
    (summary,) = _get(client, admin_headers, make_batch(one_id, JAN_5, JAN_15))["metrics"]
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
    admin_headers: dict[str, str],
    make_device: MakeDevice,
    make_batch: MakeBatch,
) -> None:
    device_id, headers = make_device("vessel-a")
    batch_id = make_batch(device_id, JAN_1)
    ahead = datetime.now(UTC) + timedelta(minutes=3)  # device clock skew, still accepted
    # Clockless readings share one server-stamped recorded_at: the later insert is "latest".
    _ingest(
        client,
        headers,
        [("temperature_c", 10, None), ("temperature_c", 20, None), ("temperature_c", 99, ahead)],
    )

    (summary,) = _get(client, admin_headers, batch_id)["metrics"]
    assert summary["count"] == 2
    assert summary["latest_value"] == 20
    assert summary["max_value"] == 20  # the reading ahead of now is excluded, as in list_readings


def test_get_unknown_batch_is_404(client: TestClient, admin_headers: dict[str, str]) -> None:
    assert client.get("/api/v1/batches/999", headers=admin_headers).status_code == 404
