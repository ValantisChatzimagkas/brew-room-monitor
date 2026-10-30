"""reading dedupe

Revision ID: a7488b9a2b00
Revises: 2c152cb14213
Create Date: 2026-10-30 12:01:42.676118

"""

from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = "a7488b9a2b00"
down_revision: str | Sequence[str] | None = "2c152cb14213"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    # A failing index build would block container start, so drop already-stored duplicates
    # first. The lowest id wins, matching first-write-wins at ingest. Both sides must satisfy
    # the index predicate so only rows the index covers are compared.
    op.execute("""
        DELETE FROM reading a USING reading b
        WHERE a.device_id = b.device_id
          AND a.metric = b.metric
          AND a.recorded_at = b.recorded_at
          AND a.recorded_at <> a.received_at
          AND b.recorded_at <> b.received_at
          AND a.id > b.id
    """)
    op.create_index(
        "uq_reading_device_metric_time",
        "reading",
        ["device_id", "metric", "recorded_at"],
        unique=True,
        postgresql_where=sa.text("recorded_at <> received_at"),
    )


def downgrade() -> None:
    """Downgrade schema. Duplicates deleted by upgrade are not restored."""
    op.drop_index(
        "uq_reading_device_metric_time",
        table_name="reading",
        postgresql_where=sa.text("recorded_at <> received_at"),
    )
