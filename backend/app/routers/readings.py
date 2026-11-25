import math
from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status
from pydantic import AwareDatetime
from sqlalchemy import func
from sqlalchemy import select as select_columns  # sqlmodel's `select` types at most 4 columns
from sqlalchemy.dialects.postgresql import insert
from sqlmodel import col, select

from app.deps import DeviceDep, SessionDep, UserDep, get_batch_or_404, owned
from app.models import (
    BucketSize,
    Device,
    IngestResult,
    Metric,
    Reading,
    ReadingBatch,
    ReadingBucket,
    ReadingPublic,
    bucket_duration,
    metric_spec,
    utcnow,
)
from app.services.batches import batch_readings_filter

router = APIRouter(prefix="/readings", tags=["readings"])

# Reject device clocks that are clearly wrong rather than storing garbage timestamps.
MAX_CLOCK_SKEW = timedelta(minutes=5)
# A chart never carries more points than the raw readings route's max `limit`.
MAX_BUCKETS = 5000
# Fixed, not the batch start or `since`: buckets stay on clock boundaries across refreshes.
_BUCKET_ORIGIN = datetime(2000, 1, 1, tzinfo=UTC)


@router.post("", status_code=status.HTTP_201_CREATED)
def ingest_readings(batch: ReadingBatch, device: DeviceDep, session: SessionDep) -> IngestResult:
    """Device-authenticated batch ingest (ESP32 / capsule sensors)."""
    now = utcnow()
    if any(r.recorded_at and r.recorded_at > now + MAX_CLOCK_SKEW for r in batch.readings):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "recorded_at is in the future")
    bad_metrics = sorted(
        {r.metric for r in batch.readings if device.kind not in metric_spec(r.metric).kinds}
    )
    if bad_metrics:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            f"{', '.join(bad_metrics)} not allowed for {device.kind} devices",
        )

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


@router.get("")
def list_readings(
    session: SessionDep,
    user: UserDep,
    device_id: int | None = None,
    batch_id: int | None = None,
    metric: Metric | None = None,
    since: datetime | None = None,
    limit: Annotated[int, Query(ge=1, le=5000)] = 500,
) -> list[ReadingPublic]:
    # A reading belongs to its device's owner; a foreign device id simply matches no rows.
    query = owned(
        select(Reading).join(Device, col(Device.id) == col(Reading.device_id)),
        col(Device.owner_id),
        user,
    )
    query = query.order_by(col(Reading.recorded_at).desc()).limit(limit)
    if device_id is not None:
        query = query.where(Reading.device_id == device_id)
    if batch_id is not None:
        query = query.where(*batch_readings_filter(get_batch_or_404(session, batch_id, user)))
    if metric is not None:
        query = query.where(Reading.metric == metric)
    if since is not None:
        query = query.where(col(Reading.recorded_at) >= since)
    return [ReadingPublic.model_validate(r) for r in session.exec(query).all()]


@router.get("/buckets")
def list_reading_buckets(
    session: SessionDep,
    user: UserDep,
    batch_id: int,
    metric: Metric,
    bucket: BucketSize,
    since: AwareDatetime | None = None,
) -> list[ReadingBucket]:
    """Average, min and max of a batch's readings per time bucket, oldest first.

    One row per non-empty bucket; buckets sit on a fixed UTC grid, so the first may start before
    the window but holds only readings inside it. Unlike `list_readings`, nothing is truncated:
    a window needing more than `MAX_BUCKETS` buckets is a 422.
    """
    batch = get_batch_or_404(session, batch_id, user)
    start = max(batch.started_at, since) if since else batch.started_at
    size = bucket_duration(bucket)
    if _bucket_count(start, batch.ended_at or utcnow(), size) > MAX_BUCKETS:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            f"More than {MAX_BUCKETS} buckets: pick a larger bucket or a shorter period",
        )

    value = col(Reading.value)
    # Built once and reused: psycopg binds each copy's params separately, and Postgres would
    # then reject the select as not in GROUP BY.
    bucket_start = func.date_bin(size, col(Reading.recorded_at), _BUCKET_ORIGIN)
    query = (
        select_columns(bucket_start, func.avg(value), func.min(value), func.max(value))
        .where(*batch_readings_filter(batch), col(Reading.metric) == metric)
        .group_by(bucket_start)
        .order_by(bucket_start)
    )
    if since is not None:
        query = query.where(col(Reading.recorded_at) >= since)
    return [
        ReadingBucket(bucket_start=start_at, avg_value=avg, min_value=low, max_value=high)
        for start_at, avg, low, high in session.execute(query).all()
    ]


def _bucket_count(start: datetime, end: datetime, size: timedelta) -> int:
    """The most grid-aligned buckets a window of this span can touch."""
    if end <= start:
        return 0
    return math.ceil((end - start) / size) + 1
