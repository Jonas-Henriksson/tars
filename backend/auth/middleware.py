"""FastAPI authentication middleware and dependencies."""
from __future__ import annotations

from typing import Any

from fastapi import Depends, HTTPException, Request, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

from backend.auth.jwt import verify_token
from backend.database import get_db
from backend.database.queries import get_row

_bearer_scheme = HTTPBearer(auto_error=False)


class CurrentUser:
    """Represents the authenticated user in a request."""

    def __init__(self, user_id: str, email: str, name: str, team_id: str = ""):
        self.id = user_id
        self.email = email
        self.name = name
        self.team_id = team_id  # Active team context

    def __repr__(self) -> str:
        return f"CurrentUser(id={self.id!r}, name={self.name!r})"


async def get_current_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> CurrentUser:
    """Extract and validate the current user from JWT token.

    Checks:
    1. Authorization: Bearer <token> header
    2. Cookie: tars_token=<token>
    3. Query param: ?token=<token> (for WebSocket connections)
    """
    token = None

    # 1. Bearer header
    if credentials:
        token = credentials.credentials

    # 2. Cookie fallback
    if not token:
        token = request.cookies.get("tars_token")

    # 3. Query param fallback (WebSocket)
    if not token:
        token = request.query_params.get("token")

    if not token:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Not authenticated",
            headers={"WWW-Authenticate": "Bearer"},
        )

    payload = verify_token(token)
    if not payload:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user_id = payload.get("sub")
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid token payload",
        )

    # Verify user still exists
    with get_db() as db:
        user = get_row(db, "users", user_id)
        if not user:
            raise HTTPException(
                status_code=status.HTTP_401_UNAUTHORIZED,
                detail="User not found",
            )

    return CurrentUser(
        user_id=user["id"],
        email=user.get("email", ""),
        name=user.get("name", ""),
        team_id=payload.get("team_id", ""),
    )


async def get_optional_user(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(_bearer_scheme),
) -> CurrentUser | None:
    """Like get_current_user but returns None instead of raising."""
    try:
        return await get_current_user(request, credentials)
    except HTTPException:
        return None


def require_team_role(
    required_role: str = "member",
) -> Any:
    """Dependency that checks the user has the required role in the active team."""

    async def checker(user: CurrentUser = Depends(get_current_user)) -> CurrentUser:
        if not user.team_id:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="No active team selected",
            )

        role_hierarchy = {"owner": 3, "admin": 2, "member": 1}

        with get_db() as db:
            row = db.execute(
                "SELECT role FROM team_members WHERE user_id = ? AND team_id = ?",
                (user.id, user.team_id),
            ).fetchone()

            if not row:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail="Not a member of this team",
                )

            user_level = role_hierarchy.get(row["role"], 0)
            required_level = role_hierarchy.get(required_role, 0)

            if user_level < required_level:
                raise HTTPException(
                    status_code=status.HTTP_403_FORBIDDEN,
                    detail=f"Requires {required_role} role or higher",
                )

        return user

    return Depends(checker)
