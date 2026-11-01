"""Verify user access tokens (JWTs) against the issuer's public keys (docs/decisions/0001)."""

import logging
from dataclasses import dataclass
from functools import lru_cache
from typing import Any

import httpx
import jwt

from app.config import Settings

logger = logging.getLogger(__name__)

# A code constant, never read from the token or env, so a token cannot choose its own algorithm.
ALGORITHM = "RS256"
LEEWAY_SECONDS = 30
HTTP_TIMEOUT_SECONDS = 5
MAX_SUBJECT_LENGTH = 255  # OIDC upper bound


class InvalidToken(Exception):
    """The token is not acceptable: the caller gets 401."""


class ProviderUnavailable(Exception):
    """The issuer's keys cannot be fetched: the caller gets 503."""


@dataclass(frozen=True)
class Identity:
    issuer: str
    subject: str


@lru_cache
def _signing_keys(issuer: str) -> jwt.PyJWKSet:
    """Fetch the issuer's keys through OIDC discovery (once per process per issuer)."""
    discovery_url = issuer.rstrip("/") + "/.well-known/openid-configuration"
    try:
        # No redirects: the issuer URL is configured, so a redirect is a fault, not a feature.
        with httpx.Client(timeout=HTTP_TIMEOUT_SECONDS, follow_redirects=False) as client:
            discovery: dict[str, Any] = client.get(discovery_url).raise_for_status().json()
            if discovery.get("issuer") != issuer:
                raise ValueError("discovery issuer mismatch")
            jwks = client.get(discovery["jwks_uri"]).raise_for_status().json()
        return jwt.PyJWKSet.from_dict(jwks)
    except (httpx.HTTPError, ValueError, KeyError, TypeError, jwt.PyJWTError) as exc:
        # Class name only: exception text can carry the URL.
        logger.warning("signing keys unavailable: %s", type(exc).__name__)
        raise ProviderUnavailable from exc


def verify_user_token(token: str, settings: Settings) -> Identity:
    issuer, audience = settings.auth_issuer, settings.auth_audience
    if not issuer or not audience:
        raise InvalidToken  # unset config fails closed, before any network call
    try:
        kid = jwt.get_unverified_header(token).get("kid")
        if not isinstance(kid, str):
            raise InvalidToken
        try:
            key = _signing_keys(issuer)[kid]
        except KeyError:
            raise InvalidToken from None
        claims = jwt.decode(
            token,
            key,
            algorithms=[ALGORITHM],
            audience=audience,
            issuer=issuer,
            leeway=LEEWAY_SECONDS,
            options={"require": ["exp", "iss", "aud", "sub"]},
        )
    except jwt.PyJWTError as exc:
        # Never the token, claims or headers.
        logger.info("user token rejected: %s", type(exc).__name__)
        raise InvalidToken from exc
    subject = claims["sub"]
    if not isinstance(subject, str) or not 1 <= len(subject) <= MAX_SUBJECT_LENGTH:
        raise InvalidToken
    return Identity(issuer=issuer, subject=subject)
