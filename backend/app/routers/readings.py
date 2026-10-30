from datetime import datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy.dialects.postgresql import insert
from sqlmodel import col, select

from app.deps import AdminDep, DeviceDep, SessionDep
from app.models import IngestResult, Metric, Reading, ReadingBatch, ReadingPublic, utcnow

router = APIRouter(prefix="/readings", tags=["readings"])

# Reject device clocks that are clearly wrong rather than storing garbage timestamps.
MAX_CLOCK_SKEW = timedelta(minutes=5)


@router.post("", status_code=status.HTTP_201_CREATED)
def ingest_readings(batch: ReadingBatch, device: DeviceDep, session: SessionDep) -> IngestResult:
    """Device-authenticated batch ingest (ESP32 / capsule sensors)."""
    now = utcnow()
    if any(r.recorded_at and r.recorded_at > now + MAX_CLOCK_SKEW for r in batch.readings):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "recorded_at is in the future")

    # A device resends a batch after a lost 201; rows already stored (see the partial unique
    # index on Reading) are skipped, new ones in the same batch still land.
    session.exec(
        insert(Reading)
        .values(
            [
                {
                    "device_id": device.id,
                    "metric": r.metric,
                    "value": r.value,
                    "recorded_at": r.recorded_at or now,
                    "received_at": now,
                }
                for r in batch.readings
            ]
        )
        .on_conflict_do_nothing()
    )
    session.commit()
    return IngestResult(accepted=len(batch.readings))


@router.get("", dependencies=[AdminDep])
def list_readings(
    session: SessionDep,
    device_id: int | None = None,
    metric: Metric | None = None,
    since: datetime | None = None,
    limit: Annotated[int, Query(ge=1, le=5000)] = 500,
) -> list[ReadingPublic]:
    query = select(Reading).order_by(col(Reading.recorded_at).desc()).limit(limit)
    if device_id is not None:
        query = query.where(Reading.device_id == device_id)
    if metric is not None:
        query = query.where(Reading.metric == metric)
    if since is not None:
        query = query.where(col(Reading.recorded_at) >= since)
    return [ReadingPublic.model_validate(r) for r in session.exec(query).all()]
