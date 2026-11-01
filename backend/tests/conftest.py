import os
from collections.abc import Callable, Iterator
from datetime import datetime
from pathlib import Path

import pytest
from alembic.config import Config
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
ADMIN_TOKEN = "test-admin-token"

os.environ.update(
    ENVIRONMENT="test",
    DATABASE_URL=TEST_DB_URL.render_as_string(hide_password=False),
    ADMIN_TOKEN=ADMIN_TOKEN,
)

from app.db import engine, get_session  # noqa: E402  env must be set first
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
def admin_headers() -> dict[str, str]:
    return {"Authorization": f"Bearer {ADMIN_TOKEN}"}


@pytest.fixture
def location_id(client: TestClient, admin_headers: dict[str, str]) -> int:
    res = client.post("/api/v1/locations", json={"name": "garage"}, headers=admin_headers)
    return int(res.json()["id"])


def _register_device(
    client: TestClient, admin_headers: dict[str, str], body: dict[str, object]
) -> tuple[int, dict[str, str]]:
    res = client.post("/api/v1/devices", json=body, headers=admin_headers)
    return int(res.json()["id"]), {"Authorization": f"Bearer {res.json()['token']}"}


@pytest.fixture
def device_headers(
    client: TestClient, admin_headers: dict[str, str], location_id: int
) -> dict[str, str]:
    return _register_device(
        client,
        admin_headers,
        {"name": "room-1", "kind": "ambient", "location_id": location_id},
    )[1]


@pytest.fixture
def in_vessel_headers(client: TestClient, admin_headers: dict[str, str]) -> dict[str, str]:
    return _register_device(client, admin_headers, {"name": "vessel-1", "kind": "in_vessel"})[1]


@pytest.fixture
def make_device(
    client: TestClient, admin_headers: dict[str, str]
) -> Callable[[str], tuple[int, dict[str, str]]]:
    """Register a new in-vessel device; returns its id and its token headers."""
    return lambda name: _register_device(client, admin_headers, {"name": name, "kind": "in_vessel"})


@pytest.fixture
def make_batch(client: TestClient, admin_headers: dict[str, str]) -> Callable[..., int]:
    """Create a batch on a device over a window (open when `ended_at` is None); returns its id."""

    def make(device_id: int, started_at: datetime, ended_at: datetime | None = None) -> int:
        body: dict[str, object] = {
            "name": "ipa",
            "device_id": device_id,
            "started_at": started_at.isoformat(),
            "ended_at": ended_at.isoformat() if ended_at else None,
        }
        res = client.post("/api/v1/batches", json=body, headers=admin_headers)
        assert res.status_code == 201
        return int(res.json()["id"])

    return make
