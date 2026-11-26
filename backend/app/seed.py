"""Demo data for a local user, through the public API only (`make seed`).

Goes through the same routes, owner scoping and payload bounds as real data, never the DB.
"""

import argparse
import logging
import math
from datetime import UTC, datetime, timedelta
from typing import Any, Protocol
from urllib.parse import parse_qs, urlsplit

import httpx

from app.config import get_settings
from app.models import Metric

logger = logging.getLogger(__name__)

LOCATION_NAME = "Demo brew room"
DEVICE_NAME = "demo-room-sensor"
BATCH_NAME = "Demo ale"
YEAST_NAME = "Demo ale yeast"
YEAST_MIN_C = 18.0
YEAST_MAX_C = 22.0
STEP = timedelta(minutes=15)
# Covers the batch window (-7 d to -1 d) and the device page's 24 h chart.
HISTORY = timedelta(days=8)
BATCH_START_AGO = timedelta(days=7)
BATCH_END_AGO = timedelta(days=1)
EXCURSION = (timedelta(hours=6), timedelta(hours=16))  # offset from batch start
EXCURSION_C = 4.5
CHUNK = 500  # ingest's max readings per request

_REDIRECT_URI = "http://localhost:3000/auth/callback"
_CLIENT_ID = "brew-local"
_SIGN_IN_FAILED = "local sign-in provider did not issue a token"


class _Response(Protocol):
    def raise_for_status(self) -> object: ...
    def json(self) -> Any: ...


class Api(Protocol):
    """What `seed` needs from a client: an `httpx.Client`, or the tests' `TestClient`.

    `TestClient` is an `httpx2.Client`, which shares httpx's API but not its type.
    """

    def get(self, url: str, *, params: dict[str, Any], headers: dict[str, str]) -> _Response: ...
    def post(self, url: str, *, json: Any, headers: dict[str, str]) -> _Response: ...


def seed(api: Api, user_headers: dict[str, str]) -> None:
    """Find or create the demo location, device and batch, then top readings up to now."""
    now = _now_on_grid()

    locations = _get(api, "/api/v1/locations", user_headers, limit=500)
    location = next((x for x in locations if x["name"].lower() == LOCATION_NAME.lower()), None)
    if location is None:
        location = _post(api, "/api/v1/locations", user_headers, {"name": LOCATION_NAME})

    devices = _get(api, "/api/v1/devices", user_headers, limit=500)
    device = next((x for x in devices if x["name"] == DEVICE_NAME), None)
    if device is None:
        body = {"name": DEVICE_NAME, "kind": "ambient", "location_id": location["id"]}
        device = _post(api, "/api/v1/devices", user_headers, body)
    else:
        # Only create and rotate return a plaintext token; no hardware holds the demo one.
        device = _post(api, f"/api/v1/devices/{device['id']}/rotate", user_headers)

    batches = _get(api, "/api/v1/batches", user_headers, device_id=device["id"])
    batch = next((x for x in batches if x["name"] == BATCH_NAME), None)
    if batch is None:
        body = {
            "name": BATCH_NAME,
            "device_id": device["id"],
            "started_at": (now - BATCH_START_AGO).isoformat(),
            "ended_at": (now - BATCH_END_AGO).isoformat(),
            "yeast_name": YEAST_NAME,
            "yeast_min_temperature_c": YEAST_MIN_C,
            "yeast_max_temperature_c": YEAST_MAX_C,
        }
        batch = _post(api, "/api/v1/batches", user_headers, body)
    # The stored window, not one recomputed from `now`: re-runs keep the same excursion.
    batch_started_at = datetime.fromisoformat(batch["started_at"])

    readings = []
    at = now - HISTORY
    while at <= now:
        for metric, value in _reading_values(at, batch_started_at).items():
            readings.append({"metric": metric, "value": value, "recorded_at": at.isoformat()})
        at += STEP
    device_headers = {"Authorization": f"Bearer {device['token']}"}
    for i in range(0, len(readings), CHUNK):
        _post(api, "/api/v1/readings", device_headers, {"readings": readings[i : i + CHUNK]})


def _now_on_grid() -> datetime:
    """Now on the STEP grid, so re-runs send the same `recorded_at` values (deduped on ingest)."""
    step = int(STEP.total_seconds())
    return datetime.fromtimestamp(int(datetime.now(UTC).timestamp()) // step * step, tz=UTC)


def _reading_values(at: datetime, batch_started_at: datetime) -> dict[Metric, float]:
    """Deterministic ambient values for `at`, well inside `metric_spec`."""
    day = 2 * math.pi * (at.hour + at.minute / 60) / 24
    temperature = 19.5 + 1.5 * math.sin(day)  # 18-21 °C: inside the yeast range
    if batch_started_at + EXCURSION[0] <= at < batch_started_at + EXCURSION[1]:
        temperature += EXCURSION_C  # 22.5-25.5 °C: an early warm spell above it
    weather = 2 * math.pi * at.timestamp() / timedelta(days=3).total_seconds()
    return {
        Metric.TEMPERATURE_C: round(temperature, 2),
        Metric.HUMIDITY_PCT: round(55 - 5 * math.sin(day), 1),
        Metric.PRESSURE_HPA: round(1013 + 3 * math.sin(weather), 1),
        Metric.BATTERY_V: round(3.9 + 0.1 * math.cos(day), 3),
    }


def _get(api: Api, path: str, headers: dict[str, str], **params: Any) -> Any:
    res = api.get(path, headers=headers, params=params)
    res.raise_for_status()
    return res.json()


def _post(api: Api, path: str, headers: dict[str, str], body: Any = None) -> Any:
    res = api.post(path, headers=headers, json=body)
    res.raise_for_status()
    return res.json()


def local_user_token(issuer: str, username: str) -> str:
    """An access token for `username` from the local provider (`firmware/README.md` recipe)."""
    try:
        with httpx.Client(timeout=10) as http:
            res = http.post(
                f"{issuer}/authorize",
                params={
                    "client_id": _CLIENT_ID,
                    "response_type": "code",
                    "redirect_uri": _REDIRECT_URI,
                    "scope": "openid",
                    "state": "x",
                },
                data={"username": username, "claims": ""},
            )
            code = parse_qs(urlsplit(res.headers.get("location", "")).query).get("code")
            if res.status_code != 302 or not code:
                raise RuntimeError(_SIGN_IN_FAILED)
            res = http.post(
                f"{issuer}/token",
                data={
                    "grant_type": "authorization_code",
                    "code": code[0],
                    "redirect_uri": _REDIRECT_URI,
                    "client_id": _CLIENT_ID,
                    "client_secret": "any",
                },
            )
            res.raise_for_status()
            token = res.json().get("access_token")
    except (httpx.HTTPError, ValueError, AttributeError):
        # `from None`: the cause would carry the response, which may hold the code or a token.
        raise RuntimeError(_SIGN_IN_FAILED) from None
    if not isinstance(token, str) or not token:
        raise RuntimeError(_SIGN_IN_FAILED)
    return token


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    logging.getLogger("httpx").setLevel(logging.WARNING)  # one line per request drowns the summary
    parser = argparse.ArgumentParser(prog="python -m app.seed", description=__doc__)
    parser.add_argument("--api-url", required=True)
    parser.add_argument("--user", default="dev")
    args = parser.parse_args(argv)

    # Both apps refuse an http:// issuer in production, so http:// means the local provider.
    issuer = get_settings().auth_issuer
    if not issuer or not issuer.startswith("http://"):
        logger.error(
            "make seed only works with the local sign-in provider (an http:// AUTH_ISSUER)"
        )
        return 1
    try:
        token = local_user_token(issuer, args.user)
        with httpx.Client(base_url=args.api_url, timeout=30) as api:
            seed(api, {"Authorization": f"Bearer {token}"})
    except RuntimeError as e:
        logger.error("%s", e)
        return 1
    except httpx.ConnectError:
        logger.error("API not reachable at %s: start make dev or make up first", args.api_url)
        return 1
    except httpx.HTTPStatusError as e:
        # Method, path and status only: the request carries a token.
        logger.error(
            "%s %s failed: %s", e.request.method, e.request.url.path, e.response.status_code
        )
        return 1
    logger.info(
        "Seeded %s/%s/%s for user %s: sign in as %s",
        LOCATION_NAME,
        DEVICE_NAME,
        BATCH_NAME,
        args.user,
        args.user,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
