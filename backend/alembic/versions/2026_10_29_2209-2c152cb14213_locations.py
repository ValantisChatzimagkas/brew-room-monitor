"""locations

Revision ID: 2c152cb14213
Revises: c2025379d38c
Create Date: 2026-10-29 22:09:06.544561

"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa
import sqlmodel


# revision identifiers, used by Alembic.
revision: str = "2c152cb14213"
down_revision: str | Sequence[str] | None = "c2025379d38c"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Postgres' default name, spelled out so downgrade can drop it.
FK_NAME = "device_location_id_fkey"


def upgrade() -> None:
    """Upgrade schema."""
    op.create_table(
        "location",
        sa.Column("name", sqlmodel.sql.sqltypes.AutoString(length=64), nullable=False),
        sa.Column("id", sa.Integer(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(
        "uq_location_name_lower", "location", [sa.literal_column("lower(name)")], unique=True
    )
    op.add_column("device", sa.Column("location_id", sa.Integer(), nullable=True))
    op.create_foreign_key(
        FK_NAME, "device", "location", ["location_id"], ["id"], ondelete="RESTRICT"
    )
    # Free-text labels that differ only in case or surrounding whitespace are one room;
    # the earliest device's spelling wins. Empty labels get no location.
    op.execute("""
        INSERT INTO location (name)
        SELECT DISTINCT ON (lower(trim(location))) trim(location)
        FROM device
        WHERE trim(location) <> ''
        ORDER BY lower(trim(location)), id
    """)
    op.execute("""
        UPDATE device SET location_id = location.id
        FROM location
        WHERE lower(trim(device.location)) = lower(location.name)
    """)
    op.drop_column("device", "location")


def downgrade() -> None:
    """Downgrade schema."""
    op.add_column(
        "device",
        sa.Column("location", sa.VARCHAR(length=64), nullable=False, server_default=""),
    )
    op.execute("""
        UPDATE device SET location = location.name
        FROM location
        WHERE device.location_id = location.id
    """)
    op.alter_column("device", "location", server_default=None)
    op.drop_constraint(FK_NAME, "device", type_="foreignkey")
    op.drop_column("device", "location_id")
    op.drop_index("uq_location_name_lower", table_name="location")
    op.drop_table("location")
