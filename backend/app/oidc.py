"""Verify user access tokens (JWTs) against the issuer's public keys (docs/decisions/0001)."""

import logging
import threading
import time
from collections.abc import Callable
from dataclasses import dataclass, field
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
JWKS_TTL_SECONDS = 3600  # keys older than this are refreshed (best effort) on the next request
JWKS_MIN_REFETCH_SECONDS = 60  # at most one fetch attempt per issuer in this window
MAX_SUBJECT_LENGTH = 255  # OIDC upper bound


class InvalidToken(Exception):
    """The token is not acceptable: the caller gets 401."""


class ProviderUnavailable(Exception):
    """The issuer's keys cannot be fetched: the caller gets 503."""


@dataclass(frozen=True)
class Identity:
    issuer: str
    subject: str


@dataclass
class _Provider:
    """Cached keys for one issuer. Endpoints are sync and share the threadpool with device ingest,
    so no request may queue behind a slow fetch: the lock is only ever tried, never waited on."""

    keys: jwt.PyJWKSet | None = None
    fetched_at: float = 0.0  # last successful fetch
    attempted_at: float | None = None  # last fetch attempt, successful or not
    lock: threading.Lock = field(default_factory=threading.Lock)


@lru_cache
def _provider(issuer: str) -> _Provider:
    return _Provider()


def _fetch_keys(issuer: str) -> jwt.PyJWKSet:
    """Fetch the issuer's keys through OIDC discovery."""
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


def _may_attempt(provider: _Provider) -> bool:
    last = provider.attempted_at
    return last is None or time.monotonic() - last >= JWKS_MIN_REFETCH_SECONDS


def _is_stale(provider: _Provider) -> bool:
    return time.monotonic() - provider.fetched_at >= JWKS_TTL_SECONDS


def _find(keys: jwt.PyJWKSet | None, kid: str) -> jwt.PyJWK | None:
    try:
        return keys[kid] if keys else None
    except KeyError:
        return None


def _refresh(provider: _Provider, issuer: str, still_needed: Callable[[], bool]) -> bool | None:
    """One gated fetch attempt: True = refreshed, False = attempt failed, None = no attempt.

    Every network attempt passes the cooldown and wins the lock without waiting, so an outage
    or a flood of unknown `kid`s cannot turn unauthenticated traffic into outbound calls.
    """
    if not _may_attempt(provider) or not provider.lock.acquire(blocking=False):
        return None
    try:
        # Another request may have refreshed while this one was getting here.
        if not _may_attempt(provider) or not still_needed():
            return None
        provider.attempted_at = time.monotonic()
        try:
            provider.keys = _fetch_keys(issuer)
        except ProviderUnavailable:
            return False
        provider.fetched_at = provider.attempted_at
        return True
    finally:
        provider.lock.release()


def _signing_key(issuer: str, kid: str) -> jwt.PyJWK:
    provider = _provider(issuer)
    if provider.keys is None:  # cold: nothing to verify with until a fetch succeeds
        _refresh(provider, issuer, lambda: provider.keys is None)
        if provider.keys is None:
            raise ProviderUnavailable
    key = _find(provider.keys, kid)
    if key is None:  # a rotation, or junk: one gated refresh
        refreshed = _refresh(provider, issuer, lambda: _find(provider.keys, kid) is None)
        key = _find(provider.keys, kid)
        if key is None:
            raise ProviderUnavailable if refreshed is False else InvalidToken
    elif _is_stale(provider):
        # A failed refresh keeps the stale keys: a brief outage only hurts cold instances.
        _refresh(provider, issuer, lambda: _is_stale(provider))
        key = _find(provider.keys, kid)
        if key is None:
            raise InvalidToken
    return key


def verify_user_token(token: str, settings: Settings) -> Identity:
    issuer, audience = settings.auth_issuer, settings.auth_audience
    if not issuer or not audience:
        raise InvalidToken  # unset config fails closed, before any network call
    try:
        kid = jwt.get_unverified_header(token).get("kid")
        if not isinstance(kid, str):
            raise InvalidToken
        key = _signing_key(issuer, kid)
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
