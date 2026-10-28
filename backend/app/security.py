import hashlib
import secrets


def new_device_token() -> str:
    return secrets.token_urlsafe(32)


def hash_token(token: str) -> str:
    # Tokens are 256-bit random, so a fast hash is enough (no bcrypt needed).
    return hashlib.sha256(token.encode()).hexdigest()
