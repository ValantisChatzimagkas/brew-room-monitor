import secrets
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, SQLModel, select

from app.config import Settings, get_settings
from app.db import get_session
from app.models import Device
from app.security import hash_token

SessionDep = Annotated[Session, Depends(get_session)]
SettingsDep = Annotated[Settings, Depends(get_settings)]

_bearer = HTTPBearer(auto_error=False)
BearerDep = Annotated[HTTPAuthorizationCredentials | None, Depends(_bearer)]

_UNAUTHORIZED = HTTPException(
    status_code=status.HTTP_401_UNAUTHORIZED,
    detail="Invalid or missing token",
    headers={"WWW-Authenticate": "Bearer"},
)


def require_admin(creds: BearerDep, settings: SettingsDep) -> None:
    expected = settings.admin_token.get_secret_value()
    if creds is None or not secrets.compare_digest(creds.credentials, expected):
        raise _UNAUTHORIZED


def current_device(creds: BearerDep, session: SessionDep) -> Device:
    if creds is None:
        raise _UNAUTHORIZED
    device = session.exec(
        select(Device).where(Device.token_hash == hash_token(creds.credentials))
    ).first()
    if device is None:
        raise _UNAUTHORIZED
    return device


def save_or_conflict(session: Session, row: SQLModel, conflict: str) -> None:
    """Commit `row`; a unique-constraint clash becomes 409 with `conflict` as the message."""
    session.add(row)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, conflict) from None
    session.refresh(row)


AdminDep = Depends(require_admin)
DeviceDep = Annotated[Device, Depends(current_device)]
