
"""Password hashing and JWT helpers for ClinOps-AI."""

from datetime import datetime, timedelta, timezone

import jwt
from pwdlib import PasswordHash

from app.config.settings import settings


password_hash = PasswordHash.recommended()
JWT_ALGORITHM = "HS256"


def _get_jwt_secret() -> str:
    secret = settings.jwt_secret_key
    if not secret or len(secret.encode("utf-8")) < 32:
        raise RuntimeError(
            "JWT_SECRET_KEY must be configured with at least 32 bytes."
        )
    if settings.jwt_algorithm != JWT_ALGORITHM:
        raise RuntimeError("JWT_ALGORITHM must be HS256.")
    return secret


def hash_password(password: str) -> str:
    """Return a secure hash of a password."""
    return password_hash.hash(password)


def verify_password(password: str, hashed_password: str) -> bool:
    """Check a password against its stored hash."""
    return password_hash.verify(password, hashed_password)


def create_access_token(subject: str, role: str) -> str:
    """Create a signed JWT containing the user ID and role."""
    if role not in {"doctor", "patient"}:
        raise ValueError("Unsupported account role.")
    secret = _get_jwt_secret()

    expires_at = datetime.now(timezone.utc) + timedelta(
        minutes=settings.access_token_expire_minutes
    )

    payload = {
        "sub": subject,
        "role": role,
        "exp": expires_at,
    }

    return jwt.encode(
        payload,
        secret,
        algorithm=JWT_ALGORITHM,
    )


def decode_access_token(token: str) -> dict:
    """Verify a JWT and return its claims."""
    secret = _get_jwt_secret()

    try:
        return jwt.decode(
            token,
            secret,
            algorithms=[JWT_ALGORITHM],
        )
    except jwt.InvalidTokenError as exc:
        raise ValueError("Invalid or expired access token.") from exc