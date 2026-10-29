from typing import Annotated

from fastapi import APIRouter, Query, status
from sqlmodel import col, select

from app.deps import AdminDep, SessionDep, save_or_conflict
from app.models import Location, LocationCreate, LocationPublic

router = APIRouter(prefix="/locations", tags=["locations"], dependencies=[AdminDep])


@router.get("")
def list_locations(
    session: SessionDep, limit: Annotated[int, Query(ge=1, le=500)] = 100
) -> list[LocationPublic]:
    locations = session.exec(select(Location).order_by(col(Location.name)).limit(limit)).all()
    return [LocationPublic.model_validate(loc) for loc in locations]


@router.post("", status_code=status.HTTP_201_CREATED)
def create_location(payload: LocationCreate, session: SessionDep) -> LocationPublic:
    location = Location.model_validate(payload)
    save_or_conflict(session, location, "Location name already exists")
    return LocationPublic.model_validate(location)
