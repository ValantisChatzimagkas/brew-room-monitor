from datetime import datetime, timedelta

import pytest
from fastapi.testclient import TestClient

from app.config import get_settings
from app.models import utcnow
from app.seed import (
    DEVICE_NAME,
    HISTORY,
    LOCATION_NAME,
    STEP,
    YEAST_MAX_C,
    YEAST_MIN_C,
    main,
    seed,
)
from tests.conftest import AUDIENCE


def test_seed_creates_fresh_demo_data(client: TestClient, user_headers: dict[str, str]) -> None:
    seed(client, user_headers)

    devices = client.get("/api/v1/devices", headers=user_headers).json()
    assert [(d["name"], d["kind"], d["location"]["name"]) for d in devices] == [
        (DEVICE_NAME, "ambient", LOCATION_NAME)
    ]
    device_id = devices[0]["id"]

    newest = client.get(
        "/api/v1/readings",
        params={"device_id": device_id, "metric": "temperature_c", "limit": 1},
        headers=user_headers,
    ).json()
    # Fresh on the dashboard: newer than the frontend's STALE_AFTER_MS (30 min).
    assert utcnow() - datetime.fromisoformat(newest[0]["recorded_at"]) < timedelta(minutes=30)

    batches = client.get(
        "/api/v1/batches", params={"device_id": device_id}, headers=user_headers
    ).json()
    assert len(batches) == 1
    batch = batches[0]
    assert batch["ended_at"] is not None
    assert (batch["yeast_min_temperature_c"], batch["yeast_max_temperature_c"]) == (
        YEAST_MIN_C,
        YEAST_MAX_C,
    )

    detail = client.get(f"/api/v1/batches/{batch['id']}", headers=user_headers).json()
    assert detail["yeast_fit"]["above_s"] > 0
    assert detail["yeast_fit"]["inside_s"] > 0
    assert detail["metrics"]


def test_seed_rerun_adds_no_duplicates_and_stays_private(
    client: TestClient, user_headers: dict[str, str], other_user_headers: dict[str, str]
) -> None:
    seed(client, user_headers)
    seed(client, user_headers)

    for path in ("/api/v1/locations", "/api/v1/devices", "/api/v1/batches"):
        assert len(client.get(path, headers=user_headers).json()) == 1, path
        assert client.get(path, headers=other_user_headers).json() == [], path
    # Resent, not doubled: one run's grid slots, plus one if the runs straddle a slot.
    temperatures = client.get(
        "/api/v1/readings", params={"metric": "temperature_c", "limit": 5000}, headers=user_headers
    ).json()
    assert len(temperatures) <= HISTORY // STEP + 2


@pytest.mark.parametrize(
    "env", [{}, {"AUTH_ISSUER": "https://tenant.example/", "AUTH_AUDIENCE": AUDIENCE}]
)
def test_main_refuses_non_local_issuer(
    env: dict[str, str], monkeypatch: pytest.MonkeyPatch, caplog: pytest.LogCaptureFixture
) -> None:
    # {}: unset, as conftest leaves it.
    for name, value in env.items():
        monkeypatch.setenv(name, value)
    get_settings.cache_clear()
    try:
        # A closed port: reaching the API would end in the "not reachable" exit instead.
        assert main(["--api-url", "http://127.0.0.1:9"]) == 1
    finally:
        get_settings.cache_clear()
    assert "only works with the local sign-in provider" in caplog.text
