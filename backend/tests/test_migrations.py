from collections.abc import Callable, Iterator
from pathlib import Path

import pytest
from alembic.config import Config
from fastapi.testclient import TestClient
from sqlalchemy import text
from sqlmodel import Session, SQLModel

from alembic import command
from app.db import engine
from tests.conftest import FakeIssuer

OWNER_SCOPE = "9bacc2a62b89"
_cfg = Config(str(Path(__file__).parents[1] / "alembic.ini"))


@pytest.fixture
def before_owner_scope(client: TestClient, session: Session) -> Iterator[None]:
    """The schema one revision before owner scoping; back at head afterwards, tables empty.

    Every Alembic step runs before the test's first request, so no open session holds a lock
    the DDL would wait on.
    """
    command.downgrade(_cfg, f"{OWNER_SCOPE}-1")
    yield
    session.close()  # releases the locks the test's requests took, or the DDL below would wait
    # Truncate first: upgrading with rows still present may abort and leave the shared test
    # database at the old revision for every later test.
    tables = ", ".join(t.name for t in SQLModel.metadata.sorted_tables)
    with engine.begin() as conn:
        conn.execute(text(f"TRUNCATE {tables} RESTART IDENTITY CASCADE"))
    command.upgrade(_cfg, "head")


def _insert_rows(issuer_url: str, user_count: int) -> None:
    with engine.begin() as conn:
        for n in range(user_count):
            conn.execute(
                text(
                    "INSERT INTO app_user (issuer, subject, created_at) "
                    "VALUES (:issuer, :sub, now())"
                ),
                {"issuer": issuer_url, "sub": f"auth0|u{n}"},
            )
        conn.execute(text("INSERT INTO location (name) VALUES ('garage')"))
        conn.execute(
            text(
                "INSERT INTO device (name, kind, token_hash, location_id, created_at) "
                "VALUES ('room-1', 'ambient', 'h', 1, now())"
            )
        )
        conn.execute(
            text(
                "INSERT INTO reading (device_id, metric, value, recorded_at, received_at) "
                "VALUES (1, 'temperature_c', 18, now(), now())"
            )
        )


def test_backfill_assigns_the_sole_user(
    client: TestClient,
    before_owner_scope: None,
    issuer: FakeIssuer,
    make_user_token: Callable[..., str],
) -> None:
    _insert_rows(issuer.url, user_count=1)
    command.upgrade(_cfg, "head")

    with engine.connect() as conn:
        owners = conn.execute(
            text("SELECT (SELECT owner_id FROM location), (SELECT owner_id FROM device)")
        ).one()
        user_id = conn.scalar(text("SELECT id FROM app_user"))
    assert tuple(owners) == (user_id, user_id)

    # The sole user's subject is `auth0|u0`: they see the migrated device and its reading.
    headers = {"Authorization": f"Bearer {make_user_token('auth0|u0')}"}
    assert [d["name"] for d in client.get("/api/v1/devices", headers=headers).json()] == ["room-1"]
    assert len(client.get("/api/v1/readings", headers=headers).json()) == 1


@pytest.mark.parametrize("user_count", [0, 2])
def test_backfill_aborts_without_exactly_one_user(
    client: TestClient, before_owner_scope: None, issuer: FakeIssuer, user_count: int
) -> None:
    _insert_rows(issuer.url, user_count)
    with pytest.raises(RuntimeError, match="exactly one"):
        command.upgrade(_cfg, "head")

    with engine.connect() as conn:
        assert conn.scalar(text("SELECT version_num FROM alembic_version")) != OWNER_SCOPE
        assert conn.scalar(text("SELECT count(*) FROM device")) == 1
        assert conn.scalar(text("SELECT count(*) FROM location")) == 1
        assert conn.scalar(text("SELECT count(*) FROM reading")) == 1
        owner_columns = conn.scalars(
            text(
                "SELECT table_name FROM information_schema.columns "
                "WHERE column_name = 'owner_id' AND table_name IN ('location', 'device')"
            )
        ).all()
    assert owner_columns == []
