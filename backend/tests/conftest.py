import os
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient
from sqlalchemy import create_engine, make_url, text
from sqlmodel import Session, SQLModel

# Tests run against real Postgres (a dedicated *_test database), never SQLite:
# timezone handling and constraints must behave exactly like production.
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
    SQLModel.metadata.drop_all(engine)
    SQLModel.metadata.create_all(engine)
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
def device_headers(client: TestClient, admin_headers: dict[str, str]) -> dict[str, str]:
    res = client.post(
        "/api/v1/devices", json={"name": "room-1", "kind": "ambient"}, headers=admin_headers
    )
    return {"Authorization": f"Bearer {res.json()['token']}"}
