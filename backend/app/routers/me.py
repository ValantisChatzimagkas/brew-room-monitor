from fastapi import APIRouter

from app.deps import UserDep
from app.models import UserPublic

router = APIRouter(prefix="/me", tags=["me"])


@router.get("")
def get_me(user: UserDep) -> UserPublic:
    return UserPublic.model_validate(user, from_attributes=True)
