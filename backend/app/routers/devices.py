from fastapi import APIRouter, HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlmodel import col, select

from app.deps import AdminDep, SessionDep
from app.models import Device, DeviceCreate, DeviceCreated, DevicePublic
from app.security import hash_token, new_device_token

router = APIRouter(prefix="/devices", tags=["devices"], dependencies=[AdminDep])


@router.get("")
def list_devices(session: SessionDep) -> list[DevicePublic]:
    devices = session.exec(select(Device).order_by(col(Device.name))).all()
    return [DevicePublic.model_validate(d) for d in devices]


@router.post("", status_code=status.HTTP_201_CREATED)
def create_device(payload: DeviceCreate, session: SessionDep) -> DeviceCreated:
    token = new_device_token()
    device = Device.model_validate(payload, update={"token_hash": hash_token(token)})
    session.add(device)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "Device name already exists") from None
    session.refresh(device)
    return DeviceCreated.model_validate(device, update={"token": token})
