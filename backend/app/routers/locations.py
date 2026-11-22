from typing import Annotated

from fastapi import APIRouter, Query, status
from sqlmodel import col, select

from app.deps import ScopeDep, SessionDep, UserDep, owned, save_or_conflict
from app.models import Location, LocationCreate, LocationPublic

router = APIRouter(prefix="/locations", tags=["locations"])


@router.get("")
def list_locations(
    session: SessionDep, scope: ScopeDep, limit: Annotated[int, Query(ge=1, le=500)] = 100
) -> list[LocationPublic]:
    query = owned(select(Location), col(Location.owner_id), scope)
    locations = session.exec(query.order_by(col(Location.name)).limit(limit)).all()
    return [LocationPublic.model_validate(loc) for loc in locations]


@router.post("", status_code=status.HTTP_201_CREATED)
def create_location(payload: LocationCreate, session: SessionDep, user: UserDep) -> LocationPublic:
    location = Location.model_validate(payload, update={"owner_id": user.id})
    save_or_conflict(session, location, "Location name already exists")
    return LocationPublic.model_validate(location)
