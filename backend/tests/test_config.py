from typing import Literal

import pytest
from pydantic import ValidationError

from app.config import Settings


@pytest.mark.parametrize("admin_token", [None, "change-me"])
def test_boots_whatever_admin_token_is_left(
    monkeypatch: pytest.MonkeyPatch, admin_token: str | None
) -> None:
    # SOL-124 retired ADMIN_TOKEN: an old .env may still set it (even the placeholder production
    # used to reject), and production must boot either way.
    if admin_token is None:
        monkeypatch.delenv("ADMIN_TOKEN", raising=False)
    else:
        monkeypatch.setenv("ADMIN_TOKEN", admin_token)
    Settings(environment="production", auth_issuer="https://tenant.example/", auth_audience="api")


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
