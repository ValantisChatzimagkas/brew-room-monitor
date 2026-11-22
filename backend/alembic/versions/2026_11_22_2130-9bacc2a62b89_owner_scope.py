"""owner scope

Revision ID: 9bacc2a62b89
Revises: 3549024a153b
Create Date: 2026-11-22 21:30:54.500050

"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "9bacc2a62b89"
down_revision: str | Sequence[str] | None = "3549024a153b"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Postgres' default names, spelled out so downgrade can drop them.
LOCATION_FK = "location_owner_id_fkey"
DEVICE_FK = "device_owner_id_fkey"


def upgrade() -> None:
    """Upgrade schema."""
    conn = op.get_bind()
    has_rows = conn.scalar(
        sa.text("SELECT EXISTS (SELECT 1 FROM location) OR EXISTS (SELECT 1 FROM device)")
    )
    owner_id: int | None = None
    if has_rows:
        # Existing rows need an owner and only a signed-in human can be one. Checked before any
        # DDL so an abort leaves nothing half-done.
        user_ids = list(conn.scalars(sa.text("SELECT id FROM app_user")))
        if len(user_ids) != 1:
            raise RuntimeError(
                f"Found {len(user_ids)} rows in app_user; this migration needs exactly one, "
                "the owner of the existing locations and devices. Sign in once with "
                "GET /api/v1/me using a Device Authorization flow token (see "
                "firmware/README.md, 'Getting a user token'), never the API Test tab token, "
                "or delete the extra app_user rows (such as one a Test tab token created), "
                "then retry. A dev database can instead be wiped with `make db-reset`."
            )
        owner_id = user_ids[0]

    op.add_column("location", sa.Column("owner_id", sa.Integer(), nullable=True))
    op.add_column("device", sa.Column("owner_id", sa.Integer(), nullable=True))
    if owner_id is not None:
        conn.execute(sa.text("UPDATE location SET owner_id = :owner"), {"owner": owner_id})
        conn.execute(sa.text("UPDATE device SET owner_id = :owner"), {"owner": owner_id})
    op.alter_column("location", "owner_id", nullable=False)
    op.alter_column("device", "owner_id", nullable=False)
    op.create_foreign_key(
        LOCATION_FK, "location", "app_user", ["owner_id"], ["id"], ondelete="RESTRICT"
    )
    op.create_foreign_key(
        DEVICE_FK, "device", "app_user", ["owner_id"], ["id"], ondelete="RESTRICT"
    )

    op.drop_index("uq_location_name_lower", table_name="location")
    op.create_index(
        "uq_location_owner_name_lower",
        "location",
        ["owner_id", sa.literal_column("lower(name)")],
        unique=True,
    )
    op.drop_constraint("device_name_key", "device", type_="unique")
    op.create_unique_constraint("uq_device_owner_name", "device", ["owner_id", "name"])


def downgrade() -> None:
    """Downgrade schema."""
    # Global uniqueness comes back, so this fails if two owners share a name: it never merges data.
    op.drop_constraint("uq_device_owner_name", "device", type_="unique")
    op.create_unique_constraint("device_name_key", "device", ["name"])
    op.drop_index("uq_location_owner_name_lower", table_name="location")
    op.create_index(
        "uq_location_name_lower", "location", [sa.literal_column("lower(name)")], unique=True
    )

    op.drop_constraint(DEVICE_FK, "device", type_="foreignkey")
    op.drop_constraint(LOCATION_FK, "location", type_="foreignkey")
    op.drop_column("device", "owner_id")
    op.drop_column("location", "owner_id")
