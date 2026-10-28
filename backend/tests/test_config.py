from typing import Literal

import pytest
from pydantic import ValidationError

from app.config import Settings


@pytest.mark.parametrize(
    ("environment", "token", "ok"),
    [
        ("production", "change-me", False),
        ("production", "x" * 31, False),
        ("production", "x" * 32, True),
        ("local", "change-me", True),
    ],
)
def test_production_requires_strong_admin_token(
    environment: Literal["local", "production"], token: str, ok: bool
) -> None:
    if ok:
        Settings(environment=environment, admin_token=token)
        return
    with pytest.raises(ValidationError) as exc:
        Settings(environment=environment, admin_token=token)
    assert token not in str(exc.value)  # the secret must not leak into startup logs
