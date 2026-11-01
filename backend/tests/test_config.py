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
    def build() -> Settings:
        return Settings(
            environment=environment,
            admin_token=token,
            auth_issuer="https://tenant.example/",
            auth_audience="api",
        )

    if ok:
        build()
        return
    with pytest.raises(ValidationError) as exc:
        build()
    assert token not in str(exc.value)  # the secret must not leak into startup logs


@pytest.mark.parametrize(
    ("environment", "issuer", "audience", "ok"),
    [
        ("local", "https://tenant.example/", None, False),
        ("local", None, "api", False),
        ("local", "", "", True),  # empty counts as unset
        ("test", None, None, True),
        ("production", None, None, False),
        ("production", "http://tenant.example/", "api", False),
        ("production", "https://tenant.example/", "api", True),
    ],
)
def test_auth_config_rules(
    environment: Literal["local", "test", "production"],
    issuer: str | None,
    audience: str | None,
    ok: bool,
) -> None:
    def build() -> Settings:
        return Settings(
            environment=environment,
            admin_token="x" * 32,
            auth_issuer=issuer,
            auth_audience=audience,
        )

    if ok:
        build()
        return
    with pytest.raises(ValidationError) as exc:
        build()
    for value in (issuer, audience):
        assert not value or value not in str(exc.value)
