import secrets
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.dialects.postgresql import insert
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Mapped
from sqlmodel import Session, SQLModel, select
from sqlmodel.sql.expression import SelectOfScalar

from app.config import Settings, get_settings
from app.db import get_session
from app.models import Device, User, utcnow
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


def _is_admin(creds: HTTPAuthorizationCredentials | None, settings: Settings) -> bool:
    expected = settings.admin_token.get_secret_value()
    return creds is not None and secrets.compare_digest(creds.credentials, expected)


def require_admin(creds: BearerDep, settings: SettingsDep) -> None:
    if not _is_admin(creds, settings):
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


def owner_scope(creds: BearerDep, session: SessionDep, settings: SettingsDep) -> User | None:
    """The caller's user, or None for the admin token (sees every owner's rows).

    Admin is checked first so the dashboard never triggers a JWKS fetch.
    """
    if _is_admin(creds, settings):
        return None
    return current_user(creds, session, settings)


def owned[T](
    query: SelectOfScalar[T], owner_column: Mapped[int], scope: User | None
) -> SelectOfScalar[T]:
    """Limit `query` to the rows `scope` owns; no limit for the admin (`scope` is None)."""
    return query if scope is None else query.where(owner_column == scope.id)


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
UserDep = Annotated[User, Depends(current_user)]
ScopeDep = Annotated[User | None, Depends(owner_scope)]
