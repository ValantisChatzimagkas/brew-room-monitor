from collections.abc import Callable
from datetime import UTC, datetime, timedelta

from fastapi.testclient import TestClient

MakeDevice = Callable[[str], tuple[int, dict[str, str]]]

JAN_1 = datetime(2026, 1, 1, tzinfo=UTC)
JAN_5 = datetime(2026, 1, 5, tzinfo=UTC)
JAN_10 = datetime(2026, 1, 10, tzinfo=UTC)
JAN_15 = datetime(2026, 1, 15, tzinfo=UTC)


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
