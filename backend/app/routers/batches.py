from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status
from sqlmodel import Session, col, select

from app.deps import AdminDep, SessionDep, save_or_conflict
from app.models import Batch, BatchCreate, BatchPublic, Device, utcnow

router = APIRouter(prefix="/batches", tags=["batches"], dependencies=[AdminDep])

_OVERLAP = "Batch overlaps another batch on this device"


@router.get("")
def list_batches(
    session: SessionDep, limit: Annotated[int, Query(ge=1, le=500)] = 100
) -> list[BatchPublic]:
    query = select(Batch).order_by(col(Batch.started_at).desc(), col(Batch.id).desc()).limit(limit)
    return [BatchPublic.model_validate(b) for b in session.exec(query).all()]


@router.post("", status_code=status.HTTP_201_CREATED)
def create_batch(payload: BatchCreate, session: SessionDep) -> BatchPublic:
    _ensure_device_exists(session, payload.device_id)
    started_at = payload.started_at or utcnow()
    _check_window(started_at, payload.ended_at)
    batch = Batch.model_validate(payload, update={"started_at": started_at})
    save_or_conflict(session, batch, _OVERLAP)
    return BatchPublic.model_validate(batch)


def _check_window(started_at: datetime, ended_at: datetime | None) -> None:
    # Also keeps an inverted range from reaching Postgres, where tstzrange raises (a 500).
    now = utcnow()
    if started_at > now or (ended_at is not None and ended_at > now):
        raise HTTPException(
            status.HTTP_422_UNPROCESSABLE_CONTENT, "Batch times cannot be in the future"
        )
    if ended_at is not None and ended_at < started_at:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "ended_at is before started_at")


def _ensure_device_exists(session: Session, device_id: int) -> None:
    # 422, not a raw FK error swallowed into a 409: the id is part of the payload the admin sent.
    if session.get(Device, device_id) is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Unknown device_id")
