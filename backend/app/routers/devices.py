from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy.orm import selectinload
from sqlmodel import Session, col, select

from app.deps import AdminDep, SessionDep, save_or_conflict
from app.models import (
    Device,
    DeviceCreate,
    DeviceCreated,
    DeviceKind,
    DevicePublic,
    DeviceUpdate,
    Location,
)
from app.security import hash_token, new_device_token

router = APIRouter(prefix="/devices", tags=["devices"], dependencies=[AdminDep])


@router.get("")
def list_devices(
    session: SessionDep, limit: Annotated[int, Query(ge=1, le=500)] = 100
) -> list[DevicePublic]:
    query = (
        select(Device)
        .options(selectinload(Device.location))  # type: ignore[arg-type]  # SQLModel types relationships as plain attributes
        .order_by(col(Device.name))
        .limit(limit)
    )
    return [DevicePublic.model_validate(d) for d in session.exec(query).all()]


@router.post("", status_code=status.HTTP_201_CREATED)
def create_device(payload: DeviceCreate, session: SessionDep) -> DeviceCreated:
    _ensure_location_exists(session, payload.location_id)
    token = new_device_token()
    device = Device.model_validate(payload, update={"token_hash": hash_token(token)})
    save_or_conflict(session, device, "Device name already exists")
    return DeviceCreated.model_validate(device, update={"token": token})


@router.patch("/{device_id}")
def update_device(device_id: int, payload: DeviceUpdate, session: SessionDep) -> DevicePublic:
    device = session.get(Device, device_id)
    if device is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Device not found")
    changes = payload.model_dump(exclude_unset=True)
    if "location_id" in changes:
        if changes["location_id"] is None and device.kind == DeviceKind.AMBIENT:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT, "ambient devices need a location_id"
            )
        _ensure_location_exists(session, changes["location_id"])
    device.sqlmodel_update(changes)
    save_or_conflict(session, device, "Device name already exists")
    return DevicePublic.model_validate(device)


def _ensure_location_exists(session: Session, location_id: int | None) -> None:
    # 422, not a raw FK error: the id is part of the payload the admin sent.
    if location_id is not None and session.get(Location, location_id) is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Unknown location_id")
