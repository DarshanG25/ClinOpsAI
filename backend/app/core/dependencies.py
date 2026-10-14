
"""Dependencies for authenticating API requests."""

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app.core.security import decode_access_token
from app.db.database import get_db
from app.models.domain import User

bearer_scheme = HTTPBearer(auto_error=False)


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> User:
    """Verify the bearer token and return its active database user."""

    unauthorized = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Authentication required or token is invalid.",
        headers={"WWW-Authenticate": "Bearer"},
    )

    if credentials is None:
        raise unauthorized

    try:
        claims = decode_access_token(credentials.credentials)
    except (ValueError, RuntimeError):
        raise unauthorized

    user_id = claims.get("sub")
    token_role = claims.get("role")

    if not isinstance(user_id, str) or not user_id:
        raise unauthorized
    if claims.get("role") not in {"doctor", "patient"}:
        raise unauthorized
    if not isinstance(claims.get("exp"), (int, float)) or isinstance(
        claims.get("exp"), bool
    ):
        raise unauthorized

    user = db.query(User).filter(User.id == user_id).first()

    if user is None or not user.is_active:
        raise unauthorized

    # Reject tokens whose role no longer matches the database account.
    if token_role != user.role:
        raise unauthorized

    return user


def require_role(*allowed_roles: str):
    """Restrict an endpoint to one or more account roles."""

    def role_checker(
        current_user: User = Depends(get_current_user),
    ) -> User:
        if current_user.role not in allowed_roles:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="You do not have permission to access this resource.",
            )
        return current_user

    return role_checker