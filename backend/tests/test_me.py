import base64
import hashlib
import hmac
import json
import time
from collections.abc import Callable
from typing import Any

import pytest
from cryptography.hazmat.primitives import serialization
from fastapi.testclient import TestClient
from sqlmodel import Session, func, select

from app import oidc
from app.config import Settings, get_settings
from app.main import app
from app.models import User
from tests.conftest import ADMIN_TOKEN, AUDIENCE, FakeIssuer

ME = "/api/v1/me"


def _count_users(session: Session) -> int:
    return session.exec(select(func.count()).select_from(User)).one()


def _b64(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode()


def _hand_built(
    header: dict[str, Any], claims: dict[str, Any], sign: Callable[[bytes], bytes]
) -> str:
    signing_input = f"{_b64(json.dumps(header).encode())}.{_b64(json.dumps(claims).encode())}"
    return f"{signing_input}.{_b64(sign(signing_input.encode()))}"


def test_me_returns_the_callers_user_id(client: TestClient, user_headers: dict[str, str]) -> None:
    first = client.get(ME, headers=user_headers)
    assert first.status_code == 200
    assert first.json() == {"id": first.json()["id"]}
    assert isinstance(first.json()["id"], int)

    assert client.get(ME, headers=user_headers).json() == first.json()


def test_one_user_row_per_identity(
    client: TestClient, session: Session, make_user_token: Callable[..., str]
) -> None:
    def call(sub: str) -> int:
        res = client.get(ME, headers={"Authorization": f"Bearer {make_user_token(sub)}"})
        assert res.status_code == 200
        return int(res.json()["id"])

    alice = call("auth0|alice")
    assert call("auth0|alice") == alice
    assert _count_users(session) == 1

    assert call("auth0|bob") != alice
    assert _count_users(session) == 2


@pytest.mark.parametrize(
    "claims",
    [
        {"aud": [AUDIENCE, "https://tenant.auth0.com/userinfo"]},  # Auth0 issues both
        {"sub": "x" * 255},
    ],
)
def test_accepts_valid_token_variants(
    client: TestClient, make_user_token: Callable[..., str], claims: dict[str, Any]
) -> None:
    res = client.get(ME, headers={"Authorization": f"Bearer {make_user_token(**claims)}"})
    assert res.status_code == 200


def _bad_authorization(
    issuer: FakeIssuer,
    make_user_token: Callable[..., str],
    device_headers: dict[str, str],
) -> dict[str, dict[str, str]]:
    now = int(time.time())
    public_pem = issuer.key.public_key().public_bytes(
        serialization.Encoding.PEM, serialization.PublicFormat.SubjectPublicKeyInfo
    )
    claims: dict[str, Any] = {
        "iss": issuer.url,
        "aud": AUDIENCE,
        "sub": "auth0|alice",
        "iat": now,
        "exp": now + 300,
    }
    # Hand-built with the real kid, so they reach jwt.decode and fail only on the RS256 pin.
    none_alg = _hand_built({"alg": "none", "typ": "JWT", "kid": issuer.kid}, claims, lambda _: b"")
    hs256 = _hand_built(
        {"alg": "HS256", "typ": "JWT", "kid": issuer.kid},
        claims,
        lambda data: hmac.new(public_pem, data, hashlib.sha256).digest(),
    )
    tokens = {
        "expired": make_user_token(exp=now - 3600),
        "wrong issuer": make_user_token(iss="https://evil.example/"),
        "wrong audience": make_user_token(aud="https://other.example"),
        "other key, real kid": issuer.sign(claims, key=issuer.other_key),
        "unknown kid": issuer.sign(claims, kid="nope"),
        "alg none": none_alg,
        "hs256 with public key": hs256,
        "missing exp": make_user_token(exp=None),
        "missing sub": make_user_token(sub=None),
        "empty sub": make_user_token(sub=""),
        "256-char sub": make_user_token(sub="x" * 256),
        "admin token": ADMIN_TOKEN,
        "not a jwt": "nope",
    }
    headers = {name: {"Authorization": f"Bearer {token}"} for name, token in tokens.items()}
    return {"no header": {}, "device token": device_headers, **headers}


def test_rejects_bad_tokens(
    client: TestClient,
    session: Session,
    issuer: FakeIssuer,
    make_user_token: Callable[..., str],
    device_headers: dict[str, str],
) -> None:
    normal_401 = client.get("/api/v1/devices")
    assert normal_401.status_code == 401
    users_before = _count_users(session)  # the device fixture's owner

    for case, headers in _bad_authorization(issuer, make_user_token, device_headers).items():
        res = client.get(ME, headers=headers)
        assert res.status_code == 401, case
        assert res.json() == normal_401.json(), case
    assert _count_users(session) == users_before


def test_user_routes_fail_closed_without_auth_config(
    client: TestClient, user_headers: dict[str, str]
) -> None:
    app.dependency_overrides[get_settings] = lambda: Settings(
        environment="test", admin_token=ADMIN_TOKEN, auth_issuer=None, auth_audience=None
    )
    assert client.get(ME, headers=user_headers).status_code == 401


def test_provider_outage_returns_503_without_leaking(
    client: TestClient, issuer: FakeIssuer, user_headers: dict[str, str]
) -> None:
    issuer.fail = True
    res = client.get(ME, headers=user_headers)
    assert res.status_code == 503
    assert res.json() == {"detail": "Sign-in provider unavailable"}
    assert issuer.url not in res.text


def test_cached_keys_survive_an_outage(
    client: TestClient,
    issuer: FakeIssuer,
    user_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert client.get(ME, headers=user_headers).status_code == 200
    hits = issuer.discovery_hits
    monkeypatch.setattr(oidc, "JWKS_TTL_SECONDS", 0)  # keys are stale; the cooldown stays
    issuer.fail = True

    for _ in range(5):
        assert client.get(ME, headers=user_headers).status_code == 200
    assert issuer.discovery_hits - hits <= 1


@pytest.mark.parametrize(("failing", "status"), [(False, 401), (True, 503)])
def test_unknown_kid_does_not_hammer_the_issuer(
    failing: bool, status: int, client: TestClient, issuer: FakeIssuer
) -> None:
    issuer.fail = failing
    claims = {"iss": issuer.url, "aud": AUDIENCE, "sub": "auth0|alice", "exp": time.time() + 300}
    for kid in ("nope-1", "nope-2"):
        res = client.get(ME, headers={"Authorization": f"Bearer {issuer.sign(claims, kid=kid)}"})
        assert res.status_code == status
    assert issuer.discovery_hits == 1
    assert issuer.jwks_hits == (0 if failing else 1)


def test_rotated_key_is_picked_up(
    client: TestClient,
    issuer: FakeIssuer,
    make_user_token: Callable[..., str],
    user_headers: dict[str, str],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    assert client.get(ME, headers=user_headers).status_code == 200
    monkeypatch.setattr(oidc, "JWKS_TTL_SECONDS", 0)
    monkeypatch.setattr(oidc, "JWKS_MIN_REFETCH_SECONDS", 0)
    issuer.rotate()

    res = client.get(ME, headers={"Authorization": f"Bearer {make_user_token()}"})
    assert res.status_code == 200
