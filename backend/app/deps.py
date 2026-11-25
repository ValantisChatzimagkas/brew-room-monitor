from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Mapped
from sqlmodel import Session, SQLModel, col, select
from sqlmodel.sql.expression import SelectOfScalar

from app.config import Settings, get_settings
from app.db import get_session
from app.models import Batch, Device, User, utcnow
from app.oidc import InvalidToken, ProviderUnavailable, verify_user_token
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
_PROVIDER_UNAVAILABLE = HTTPException(
    status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Sign-in provider unavailable"
)


def current_device(creds: BearerDep, session: SessionDep) -> Device:
    if creds is None:
        raise _UNAUTHORIZED
    device = session.exec(
        select(Device).where(Device.token_hash == hash_token(creds.credentials))
    ).first()
    if device is None:
        raise _UNAUTHORIZED
    return device


def current_user(creds: BearerDep, session: SessionDep, settings: SettingsDep) -> User:
    if creds is None:
        raise _UNAUTHORIZED
    try:
        identity = verify_user_token(creds.credentials, settings)
    except InvalidToken:
        raise _UNAUTHORIZED from None
    except ProviderUnavailable:
        raise _PROVIDER_UNAVAILABLE from None
    same_identity = (User.issuer == identity.issuer) & (User.subject == identity.subject)
    user = session.exec(select(User).where(same_identity)).first()
    if user is None:
        # First request from this identity. ON CONFLICT lets concurrent first requests converge on
        # one row; created_at is explicit because a Core insert skips `default_factory`.
        session.exec(
            insert(User)
            .values(issuer=identity.issuer, subject=identity.subject, created_at=utcnow())
            .on_conflict_do_nothing(constraint="uq_app_user_issuer_subject")
        )
        session.commit()
        user = session.exec(select(User).where(same_identity)).one()
    return user


def owned[T](query: SelectOfScalar[T], owner_column: Mapped[int], user: User) -> SelectOfScalar[T]:
    """Limit `query` to the rows `user` owns."""
    return query.where(owner_column == user.id)


def save_or_conflict(session: Session, row: SQLModel, conflict: str) -> None:
    """Commit `row`; a unique-constraint clash becomes 409 with `conflict` as the message."""
    session.add(row)
    try:
        session.commit()
    except IntegrityError:
        session.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, conflict) from None
    session.refresh(row)


def get_batch_or_404(session: Session, batch_id: int, user: User) -> Batch:
    """The batch, or 404. Joined to its device so a foreign owner's batch is a 404 too."""
    batch = session.exec(
        owned(
            select(Batch)
            .join(Device, col(Device.id) == col(Batch.device_id))
            .where(Batch.id == batch_id),
            col(Device.owner_id),
            user,
        )
    ).first()
    if batch is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Batch not found")
    return batch


DeviceDep = Annotated[Device, Depends(current_device)]
UserDep = Annotated[User, Depends(current_user)]
