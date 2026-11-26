from datetime import UTC, datetime, timedelta
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy import ColumnElement, FrameClause, FrameClauseType, func, or_
from sqlalchemy import select as select_columns  # sqlmodel's `select` types at most 4 columns
from sqlalchemy.dialects.postgresql import aggregate_order_by
from sqlmodel import Session, col, select

from app.deps import SessionDep, UserDep, get_batch_or_404, owned, save_or_conflict
from app.models import (
    Batch,
    BatchCreate,
    BatchDetail,
    BatchPublic,
    BatchUpdate,
    Device,
    Metric,
    MetricSummary,
    Reading,
    TemperatureNote,
    User,
    YeastFit,
    utcnow,
)
from app.services.batches import batch_readings_filter
from app.services.insights import (
    EARLY_HOT_MARGIN_C,
    EARLY_PHASE,
    LATE_WARM_FROM,
    SHARP_DROP_WINDOW,
    TemperatureStats,
    temperature_notes,
)

router = APIRouter(prefix="/batches", tags=["batches"])

_OVERLAP = "Batch overlaps another batch on this device"
_REVOKED = "Device is revoked"
# Far below any brew, and far above what Postgres timestamptz rejects with a 500.
_EARLIEST = datetime(2000, 1, 1, tzinfo=UTC)
# A reading stands for the time until the next one; a longer gap means the sensor was off, so the
# earlier reading counts at most this long.
_READING_SPAN_CAP = timedelta(hours=1)


@router.get("")
def list_batches(
    session: SessionDep,
    user: UserDep,
    device_id: int | None = None,
    limit: Annotated[int, Query(ge=1, le=500)] = 100,
) -> list[BatchPublic]:
    # A foreign device id simply matches no rows, like an unknown one.
    query = owned(
        select(Batch).join(Device, col(Device.id) == col(Batch.device_id)),
        col(Device.owner_id),
        user,
    )
    if device_id is not None:
        query = query.where(col(Batch.device_id) == device_id)
    query = query.order_by(col(Batch.started_at).desc(), col(Batch.id).desc()).limit(limit)
    return [BatchPublic.model_validate(b) for b in session.exec(query).all()]


@router.get("/{batch_id}")
def get_batch(batch_id: int, session: SessionDep, user: UserDep) -> BatchDetail:
    batch = get_batch_or_404(session, batch_id, user)
    yeast_fit, notes = _yeast_insights(session, batch)
    return BatchDetail(
        **BatchPublic.model_validate(batch).model_dump(),
        metrics=_summarize_metrics(session, batch),
        yeast_fit=yeast_fit,
        notes=notes,
    )


@router.post("", status_code=status.HTTP_201_CREATED)
def create_batch(payload: BatchCreate, session: SessionDep, user: UserDep) -> BatchPublic:
    device = _ensure_device_exists(session, payload.device_id, user)
    started_at = payload.started_at or utcnow()
    _check_window(started_at, payload.ended_at)
    _check_yeast_range(payload.yeast_min_temperature_c, payload.yeast_max_temperature_c)
    _check_not_revoked(device)
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
    _check_yeast_range(
        changes.get("yeast_min_temperature_c", batch.yeast_min_temperature_c),
        changes.get("yeast_max_temperature_c", batch.yeast_max_temperature_c),
    )
    # Only reopening an ended batch starts it again; `ended_at: null` on an open one is a no-op.
    if batch.ended_at is not None and "ended_at" in changes and changes["ended_at"] is None:
        _check_not_revoked(session.get_one(Device, batch.device_id))
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


def _check_yeast_range(low: float | None, high: float | None) -> None:
    if (low is None) != (high is None):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "Set both yeast temperature bounds or neither"
        )
    if low is not None and high is not None and low > high:
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT,
            "yeast_min_temperature_c is above yeast_max_temperature_c",
        )


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


def _yeast_insights(
    session: Session, batch: Batch
) -> tuple[YeastFit | None, list[TemperatureNote]]:
    low, high = batch.yeast_min_temperature_c, batch.yeast_max_temperature_c
    if low is None or high is None:
        return None, []
    recorded_at = col(Reading.recorded_at)
    # The window runs after WHERE, so a reading outside the batch is never a neighbour. The newest
    # has no next reading, so lead() defaults to its own time and it spans 0 s (a NULL would not do:
    # LEAST ignores NULLs and would give it the cap). Ties are ordered by id, as in
    # _summarize_metrics.
    next_at = func.lead(recorded_at, 1, recorded_at).over(order_by=(recorded_at, col(Reading.id)))
    # Highest reading in the preceding window, that reading's own time included (RANGE is
    # inclusive at both ends), minus this one: how far it fell.
    window_max = func.max(col(Reading.value)).over(
        order_by=recorded_at,
        range_=FrameClause(
            SHARP_DROP_WINDOW, None, FrameClauseType.PRECEDING, FrameClauseType.CURRENT
        ),
    )
    spans = (
        select_columns(
            col(Reading.value).label("value"),
            recorded_at.label("recorded_at"),
            func.least(
                func.extract("epoch", next_at - recorded_at), _READING_SPAN_CAP.total_seconds()
            ).label("span_s"),
            (window_max - col(Reading.value)).label("drop_c"),
        )
        .where(*batch_readings_filter(batch), col(Reading.metric) == Metric.TEMPERATURE_C)
        .subquery()
    )
    value, span_s, at = spans.c.value, spans.c.span_s, spans.c.recorded_at
    early = at < batch.started_at + EARLY_PHASE
    late = at >= batch.started_at + EARLY_PHASE
    late_warm = at >= batch.started_at + LATE_WARM_FROM

    def seconds(*where: ColumnElement[bool]) -> ColumnElement[float]:
        return func.coalesce(func.sum(span_s).filter(*where), 0)

    # No GROUP BY, so a window without temperature readings still gives one row of zeros.
    query = select_columns(
        func.count().label("reading_count"),
        func.count().filter(or_(value < low, value > high)).label("outside_count"),
        seconds(value < low).label("below_s"),
        seconds(value.between(low, high)).label("inside_s"),  # bounds are inside
        seconds(value > high).label("above_s"),
        seconds(value > high, early).label("early_above_s"),
        seconds(value >= high + EARLY_HOT_MARGIN_C, early).label("early_hot_s"),
        seconds(value < low, late).label("late_below_s"),
        func.count().filter(value > high, late_warm).label("late_above_count"),
        seconds(value > high, late_warm).label("late_above_s"),
        func.coalesce(func.max(spans.c.drop_c), 0).label("max_drop_c"),
    )
    stats = TemperatureStats(**session.execute(query).one()._mapping)
    fit = YeastFit(
        below_s=round(stats.below_s), inside_s=round(stats.inside_s), above_s=round(stats.above_s)
    )
    return fit, temperature_notes(stats)


def _ensure_device_exists(session: Session, device_id: int, user: User) -> Device:
    # 422, not a raw FK error swallowed into a 409: the id is part of the payload the caller sent.
    # Another owner's device counts as unknown, so its id is not revealed.
    query = owned(select(Device).where(Device.id == device_id), col(Device.owner_id), user)
    device = session.exec(query).first()
    if device is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Unknown device_id")
    return device


def _check_not_revoked(device: Device) -> None:
    if device.revoked_at is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, _REVOKED)
