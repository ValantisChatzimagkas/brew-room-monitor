import json
import os
import threading
import time
from collections.abc import Callable, Iterator
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

import jwt
import pytest
from alembic.config import Config
from cryptography.hazmat.primitives.asymmetric import rsa
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, make_url, text
from sqlmodel import Session, SQLModel

from alembic import command

# Tests run against real Postgres (a dedicated *_test database), never SQLite:
# timezone handling and constraints must behave exactly like production. The schema comes from
# the Alembic migrations, so a wrong migration fails the suite instead of production.
_base_url = make_url(
    os.environ.get("DATABASE_URL", "postgresql+psycopg://brew:brew@localhost:5432/brew")
)
TEST_DB_URL = _base_url.set(database=f"{_base_url.database}_test")
LEFTOVER_ADMIN_TOKEN = "test-admin-token"
AUDIENCE = "https://api.brew.test"

os.environ.update(
    ENVIRONMENT="test",
    DATABASE_URL=TEST_DB_URL.render_as_string(hide_password=False),
    # Simulates an ADMIN_TOKEN left in an old .env (retired by SOL-124): the app must ignore it,
    # and test_auth.py / test_me.py check it gets the generic 401.
    ADMIN_TOKEN=LEFTOVER_ADMIN_TOKEN,
)
# The Makefile exports the root .env into pytest: a developer's real tenant must not leak in.
for _name in ("AUTH_ISSUER", "AUTH_AUDIENCE"):
    os.environ.pop(_name, None)

from app.config import Settings, get_settings  # noqa: E402  env must be set first
from app.db import engine, get_session  # noqa: E402
from app.main import app  # noqa: E402


@pytest.fixture(scope="session", autouse=True)
def _database() -> Iterator[None]:
    admin = create_engine(_base_url, isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        exists = conn.scalar(
            text("SELECT 1 FROM pg_database WHERE datname = :n"), {"n": TEST_DB_URL.database}
        )
        if not exists:
            conn.execute(text(f'CREATE DATABASE "{TEST_DB_URL.database}"'))
    admin.dispose()
    # Wipe the schema (not just the tables) so a leftover alembic_version or old tables can't
    # make `upgrade head` fail.
    with engine.begin() as conn:
        conn.execute(text("DROP SCHEMA public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
    command.upgrade(Config(str(Path(__file__).parents[1] / "alembic.ini")), "head")
    yield
    engine.dispose()


@pytest.fixture
def session() -> Iterator[Session]:
    with Session(engine) as s:
        yield s
    tables = ", ".join(t.name for t in SQLModel.metadata.sorted_tables)
    with engine.begin() as conn:
        conn.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))


@pytest.fixture
def client(session: Session) -> Iterator[TestClient]:
    app.dependency_overrides[get_session] = lambda: session
    with TestClient(app) as c:
        yield c
    app.dependency_overrides.clear()


@pytest.fixture
def location_id(client: TestClient, user_headers: dict[str, str]) -> int:
    res = client.post("/api/v1/locations", json={"name": "garage"}, headers=user_headers)
    return int(res.json()["id"])


def _register_device(
    client: TestClient, user_headers: dict[str, str], body: dict[str, object]
) -> tuple[int, dict[str, str]]:
    res = client.post("/api/v1/devices", json=body, headers=user_headers)
    return int(res.json()["id"]), {"Authorization": f"Bearer {res.json()['token']}"}


@pytest.fixture
def device_headers(
    client: TestClient, user_headers: dict[str, str], location_id: int
) -> dict[str, str]:
    return _register_device(
        client,
        user_headers,
        {"name": "room-1", "kind": "ambient", "location_id": location_id},
    )[1]


@pytest.fixture
def in_vessel_headers(client: TestClient, user_headers: dict[str, str]) -> dict[str, str]:
    return _register_device(client, user_headers, {"name": "vessel-1", "kind": "in_vessel"})[1]


@pytest.fixture
def make_device(
    client: TestClient, user_headers: dict[str, str]
) -> Callable[[str], tuple[int, dict[str, str]]]:
    """Register a new in-vessel device for alice; returns its id and its token headers."""
    return lambda name: _register_device(client, user_headers, {"name": name, "kind": "in_vessel"})


@pytest.fixture
def make_batch(client: TestClient, user_headers: dict[str, str]) -> Callable[..., int]:
    """Create a batch on a device over a window (open when `ended_at` is None); returns its id."""

    def make(
        device_id: int,
        started_at: datetime,
        ended_at: datetime | None = None,
        *,
        headers: dict[str, str] | None = None,
        **fields: object,
    ) -> int:
        body: dict[str, object] = {
            "name": "ipa",
            "device_id": device_id,
            "started_at": started_at.isoformat(),
            "ended_at": ended_at.isoformat() if ended_at else None,
            **fields,
        }
        res = client.post("/api/v1/batches", json=body, headers=headers or user_headers)
        assert res.status_code == 201
        return int(res.json()["id"])

    return make


class FakeIssuer:
    """A real HTTP OIDC issuer on localhost: discovery document + JWKS of a throwaway RSA key."""

    def __init__(self) -> None:
        self.key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self.other_key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self.kid = "key-1"
        self.fail = False  # discovery and JWKS answer 500: a provider outage
        self.discovery_hits = 0
        self.jwks_hits = 0
        issuer = self

        class Handler(BaseHTTPRequestHandler):
            def do_GET(self) -> None:
                if self.path == "/.well-known/openid-configuration":
                    issuer.discovery_hits += 1
                    body: dict[str, Any] = {"issuer": issuer.url, "jwks_uri": issuer.url + "jwks"}
                elif self.path == "/jwks":
                    issuer.jwks_hits += 1
                    body = {"keys": [issuer.jwk()]}
                else:
                    self.send_error(404)
                    return
                if issuer.fail:
                    self.send_error(500)
                    return
                payload = json.dumps(body).encode()
                self.send_response(200)
                self.send_header("Content-Type", "application/json")
                self.send_header("Content-Length", str(len(payload)))
                self.end_headers()
                self.wfile.write(payload)

            def log_message(self, format: str, *args: Any) -> None:
                pass

        self._server = ThreadingHTTPServer(("127.0.0.1", 0), Handler)
        # Trailing slash on purpose: Auth0's `iss` has one, so the exact-match and
        # discovery-URL paths both run.
        self.url = f"http://127.0.0.1:{self._server.server_port}/"
        self._thread = threading.Thread(target=self._server.serve_forever)
        self._thread.start()

    def jwk(self) -> dict[str, Any]:
        public = jwt.algorithms.RSAAlgorithm.to_jwk(self.key.public_key(), as_dict=True)
        return {**public, "kid": self.kid, "use": "sig", "alg": "RS256"}

    def rotate(self) -> None:
        """Publish a new signing key under a new kid (the old one is gone)."""
        self.key = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        self.kid = "key-2"

    def sign(
        self,
        claims: dict[str, Any],
        *,
        key: rsa.RSAPrivateKey | None = None,
        kid: str | None = None,
        alg: str = "RS256",
    ) -> str:
        return jwt.encode(claims, key or self.key, algorithm=alg, headers={"kid": kid or self.kid})

    def close(self) -> None:
        self._server.shutdown()
        self._server.server_close()
        self._thread.join()


@pytest.fixture
def issuer() -> Iterator[FakeIssuer]:
    fake = FakeIssuer()
    app.dependency_overrides[get_settings] = lambda: Settings(
        environment="test",
        auth_issuer=fake.url,
        auth_audience=AUDIENCE,
    )
    yield fake
    fake.close()


@pytest.fixture
def make_user_token(issuer: FakeIssuer) -> Callable[..., str]:
    """A valid token for `sub`; `claims` override or add claims, a `None` value drops one."""

    def make(sub: str = "auth0|alice", **claims: Any) -> str:
        now = int(time.time())
        base: dict[str, Any] = {
            "iss": issuer.url,
            "aud": AUDIENCE,
            "sub": sub,
            "iat": now,
            "exp": now + 300,
        }
        merged = {**base, **claims}
        return issuer.sign({k: v for k, v in merged.items() if v is not None})

    return make


@pytest.fixture
def user_headers(make_user_token: Callable[..., str]) -> dict[str, str]:
    return {"Authorization": f"Bearer {make_user_token()}"}


@pytest.fixture
def other_user_headers(make_user_token: Callable[..., str]) -> dict[str, str]:
    return {"Authorization": f"Bearer {make_user_token('auth0|bob')}"}
