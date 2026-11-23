from sqlalchemy import ColumnElement
from sqlmodel import col

from app.models import Batch, Reading, utcnow


def batch_readings_filter(batch: Batch) -> tuple[ColumnElement[bool], ...]:
    """Conditions selecting a batch's readings: its device within [started_at, ended_at).

    Membership is derived, not stamped. Start is inclusive, end exclusive, and an open batch
    runs to now.
    """
    return (
        col(Reading.device_id) == batch.device_id,
        col(Reading.recorded_at) >= batch.started_at,
        col(Reading.recorded_at) < (batch.ended_at or utcnow()),
    )
