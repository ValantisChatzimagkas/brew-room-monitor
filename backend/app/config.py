from functools import lru_cache
from typing import Literal, Self

from pydantic import SecretStr, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """All config comes from env vars (locally the root .env, loaded by make).

    Never read os.environ elsewhere.
    """

    # hide_input_in_errors: otherwise a validation error prints the raw env values (secrets).
    model_config = SettingsConfigDict(extra="ignore", hide_input_in_errors=True)

    environment: Literal["local", "test", "production"] = "local"
    database_url: str = "postgresql+psycopg://brew:brew@localhost:5432/brew"
    # Shared secret for the frontend server / admin calls. Devices use their own per-device tokens.
    admin_token: SecretStr
    # User sign-in (docs/decisions/0001): the issuer must equal the token's `iss` exactly.
    # Unset (or empty) means user routes return 401, never "skip verification".
    auth_issuer: str | None = None
    auth_audience: str | None = None

    @property
    def is_production(self) -> bool:
        return self.environment == "production"

    @model_validator(mode="after")
    def _strong_admin_token_in_production(self) -> Self:
        # Refuse to boot with the `.env.example` placeholder or a guessable token.
        if self.is_production and len(self.admin_token.get_secret_value()) < 32:
            raise ValueError("ADMIN_TOKEN must be at least 32 characters in production")
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()  # values come from env
