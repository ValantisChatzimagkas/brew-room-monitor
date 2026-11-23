from datetime import UTC, datetime
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import func
from sqlalchemy import select as select_columns  # sqlmodel's `select` types at most 4 columns
from sqlalchemy.dialects.postgresql import aggregate_order_by
from sqlmodel import Session, col, select

from app.deps import ScopeDep, SessionDep, UserDep, get_batch_or_404, owned, save_or_conflict
from app.models import (
    Batch,
    BatchCreate,
    BatchDetail,
    BatchPublic,
    BatchUpdate,
    Device,
    MetricSummary,
    Reading,
    User,
    utcnow,
)
from app.services.batches import batch_readings_filter

router = APIRouter(prefix="/batches", tags=["batches"])

_OVERLAP = "Batch overlaps another batch on this device"
# Far below any brew, and far above what Postgres timestamptz rejects with a 500.
_EARLIEST = datetime(2000, 1, 1, tzinfo=UTC)


@router.get("")
def list_batches(
    session: SessionDep, scope: ScopeDep, limit: Annotated[int, Query(ge=1, le=500)] = 100
) -> list[BatchPublic]:
    query = (
        owned(
            select(Batch).join(Device, col(Device.id) == col(Batch.device_id)),
            col(Device.owner_id),
            scope,
        )
        .order_by(col(Batch.started_at).desc(), col(Batch.id).desc())
        .limit(limit)
    )
    return [BatchPublic.model_validate(b) for b in session.exec(query).all()]


@router.get("/{batch_id}")
def get_batch(batch_id: int, session: SessionDep, scope: ScopeDep) -> BatchDetail:
    batch = get_batch_or_404(session, batch_id, scope)
    return BatchDetail(
        **BatchPublic.model_validate(batch).model_dump(),
        metrics=_summarize_metrics(session, batch),
    )


@router.post("", status_code=status.HTTP_201_CREATED)
def create_batch(payload: BatchCreate, session: SessionDep, user: UserDep) -> BatchPublic:
    _ensure_device_exists(session, payload.device_id, user)
    started_at = payload.started_at or utcnow()
    _check_window(started_at, payload.ended_at)
    batch = Batch.model_validate(payload, update={"started_at": started_at})
    save_or_conflict(session, batch, _OVERLAP)
    return BatchPublic.model_validate(batch)


@router.patch("/{batch_id}")
def update_batch(
    batch_id: int, payload: BatchUpdate, session: SessionDep, user: UserDep
) -> BatchPublic:
    batch = get_batch_or_404(session, batch_id, user)
    changes = payload.model_dump(exclude_unset=True)
    _check_window(
        changes.get("started_at", batch.started_at), changes.get("ended_at", batch.ended_at)
    )
    batch.sqlmodel_update(changes)
    save_or_conflict(session, batch, _OVERLAP)
    return BatchPublic.model_validate(batch)


def _check_window(started_at: datetime, ended_at: datetime | None) -> None:
    # Also keeps an inverted range from reaching Postgres, where tstzrange raises (a 500).
    now = utcnow()
    if started_at < _EARLIEST:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "started_at is too far in the past"
        )
    if started_at > now or (ended_at is not None and ended_at > now):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "Batch times cannot be in the future"
        )
    if ended_at is not None and ended_at < started_at:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "ended_at is before started_at")


def _summarize_metrics(session: Session, batch: Batch) -> list[MetricSummary]:
    value, recorded_at = col(Reading.value), col(Reading.recorded_at)
    # Latest = newest recorded_at; the higher id (later insert) breaks a tie between clockless
    # readings, which share the server's receive time.
    latest = func.array_agg(aggregate_order_by(value, recorded_at.desc(), col(Reading.id).desc()))
    query = (
        select_columns(
            col(Reading.metric),
            func.count(),
            func.min(value),
            func.max(value),
            func.avg(value),
            latest[1],
            func.max(recorded_at),
        )
        .where(*batch_readings_filter(batch))
        .group_by(col(Reading.metric))
        .order_by(col(Reading.metric))
    )
    return [
        MetricSummary(
            metric=metric,
            count=count,
            min_value=low,
            max_value=high,
            avg_value=mean,
            latest_value=latest_value,
            latest_recorded_at=latest_at,
        )
        for metric, count, low, high, mean, latest_value, latest_at in session.execute(query).all()
    ]


def _ensure_device_exists(session: Session, device_id: int, user: User) -> None:
    # 422, not a raw FK error swallowed into a 409: the id is part of the payload the caller sent.
    # Another owner's device counts as unknown, so its id is not revealed.
    query = owned(select(Device).where(Device.id == device_id), col(Device.owner_id), user)
    if session.exec(query).first() is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Unknown device_id")
