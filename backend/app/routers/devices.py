from typing import Annotated

from fastapi import APIRouter, HTTPException, Query, status
from sqlalchemy.orm import selectinload
from sqlmodel import Session, col, select

from app.deps import ScopeDep, SessionDep, UserDep, owned, save_or_conflict
from app.models import (
    Device,
    DeviceCreate,
    DeviceCreated,
    DeviceKind,
    DevicePublic,
    DeviceUpdate,
    Location,
    User,
    utcnow,
)
from app.security import hash_token, new_device_token

router = APIRouter(prefix="/devices", tags=["devices"])


@router.get("")
def list_devices(
    session: SessionDep, scope: ScopeDep, limit: Annotated[int, Query(ge=1, le=500)] = 100
) -> list[DevicePublic]:
    query = (
        owned(select(Device), col(Device.owner_id), scope)
        .options(selectinload(Device.location))  # type: ignore[arg-type]  # SQLModel types relationships as plain attributes
        .order_by(col(Device.name))
        .limit(limit)
    )
    return [DevicePublic.model_validate(d) for d in session.exec(query).all()]


@router.post("", status_code=status.HTTP_201_CREATED)
def create_device(payload: DeviceCreate, session: SessionDep, user: UserDep) -> DeviceCreated:
    _ensure_location_exists(session, payload.location_id, user)
    token = new_device_token()
    device = Device.model_validate(
        payload, update={"token_hash": hash_token(token), "owner_id": user.id}
    )
    save_or_conflict(session, device, "Device name already exists")
    return DeviceCreated.model_validate(device, update={"token": token})


@router.patch("/{device_id}")
def update_device(
    device_id: int, payload: DeviceUpdate, session: SessionDep, user: UserDep
) -> DevicePublic:
    device = _get_device(session, device_id, user)
    changes = payload.model_dump(exclude_unset=True)
    if "location_id" in changes:
        if changes["location_id"] is None and device.kind == DeviceKind.AMBIENT:
            raise HTTPException(
                status.HTTP_422_UNPROCESSABLE_CONTENT, "ambient devices need a location_id"
            )
        _ensure_location_exists(session, changes["location_id"], user)
    device.sqlmodel_update(changes)
    save_or_conflict(session, device, "Device name already exists")
    return DevicePublic.model_validate(device)


@router.post("/{device_id}/revoke")
def revoke_device(device_id: int, session: SessionDep, user: UserDep) -> DevicePublic:
    device = _get_device(session, device_id, user)
    if device.revoked_at is None:
        # Replacing the hash, not `revoked_at`, is what locks the device out: the old token dies
        # under any code version, so a rollback can't readmit it. Its plaintext is never kept.
        device.revoked_at = utcnow()
        device.token_hash = hash_token(new_device_token())
        session.add(device)
        session.commit()
        session.refresh(device)
    return DevicePublic.model_validate(device)


@router.post("/{device_id}/rotate")
def rotate_device_token(device_id: int, session: SessionDep, user: UserDep) -> DeviceCreated:
    device = _get_device(session, device_id, user)
    token = new_device_token()
    device.token_hash = hash_token(token)
    device.revoked_at = None
    session.add(device)
    session.commit()
    session.refresh(device)
    return DeviceCreated.model_validate(device, update={"token": token})


def _get_device(session: Session, device_id: int, user: User) -> Device:
    query = owned(select(Device).where(Device.id == device_id), col(Device.owner_id), user)
    device = session.exec(query).first()
    if device is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Device not found")
    return device


def _ensure_location_exists(session: Session, location_id: int | None, user: User) -> None:
    # 422, not a raw FK error: the id is part of the payload the caller sent. Another owner's
    # location counts as unknown, so its id is not revealed.
    if location_id is None:
        return
    query = owned(select(Location).where(Location.id == location_id), col(Location.owner_id), user)
    if session.exec(query).first() is None:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, "Unknown location_id")
