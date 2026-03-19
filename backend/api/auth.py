"""Auth API — registration, login, team management."""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from pydantic import BaseModel

from backend.auth.jwt import create_token, hash_password, verify_password
from backend.auth.middleware import CurrentUser, get_current_user, require_team_role
from backend.database import get_db
from backend.database.queries import (
    generate_id, get_row, get_team_members, get_user_teams,
    insert_row, list_rows, now_iso, update_row,
)

router = APIRouter(prefix="/api/auth", tags=["auth"])


# ---------------------------------------------------------------------------
# Models
# ---------------------------------------------------------------------------

class RegisterRequest(BaseModel):
    email: str
    name: str
    password: str


class LoginRequest(BaseModel):
    email: str
    password: str


class TeamCreate(BaseModel):
    name: str


class TeamInvite(BaseModel):
    email: str
    role: str = "member"


class PreferencesUpdate(BaseModel):
    theme: str = ""
    dark_mode: bool | None = None
    density: str = ""


# ---------------------------------------------------------------------------
# User endpoints
# ---------------------------------------------------------------------------

@router.post("/register", status_code=201)
async def register(body: RegisterRequest, response: Response):
    """Register a new user account."""
    with get_db() as db:
        # Check if email already exists
        existing = db.execute(
            "SELECT id FROM users WHERE email = ?", (body.email,)
        ).fetchone()
        if existing:
            raise HTTPException(status_code=409, detail="Email already registered")

        user_id = generate_id()
        insert_row(db, "users", {
            "id": user_id,
            "email": body.email,
            "name": body.name,
            "password_hash": hash_password(body.password),
        })

    token = create_token({"sub": user_id, "email": body.email, "name": body.name})
    response.set_cookie(
        "tars_token", token,
        httponly=True, samesite="lax", max_age=86400 * 7,
    )
    return {"token": token, "user": {"id": user_id, "email": body.email, "name": body.name}}


@router.post("/login")
async def login(body: LoginRequest, response: Response):
    """Log in with email and password."""
    with get_db() as db:
        user = db.execute(
            "SELECT * FROM users WHERE email = ?", (body.email,)
        ).fetchone()

        if not user or not verify_password(body.password, user["password_hash"]):
            raise HTTPException(status_code=401, detail="Invalid credentials")

        # Update last login
        db.execute(
            "UPDATE users SET last_login_at = ? WHERE id = ?",
            (now_iso(), user["id"]),
        )

    # Get user's teams for the token
    with get_db() as db:
        teams = get_user_teams(db, user["id"])

    token = create_token({
        "sub": user["id"],
        "email": user["email"],
        "name": user["name"],
        "team_id": teams[0]["id"] if teams else "",
    })
    response.set_cookie(
        "tars_token", token,
        httponly=True, samesite="lax", max_age=86400 * 7,
    )
    return {
        "token": token,
        "user": {"id": user["id"], "email": user["email"], "name": user["name"]},
        "teams": [{"id": t["id"], "name": t["name"], "role": t["member_role"]} for t in teams],
    }


@router.post("/logout")
async def logout(response: Response):
    """Clear the auth cookie."""
    response.delete_cookie("tars_token")
    return {"message": "Logged out"}


@router.get("/me")
async def get_me(user: CurrentUser = Depends(get_current_user)):
    """Get current user profile."""
    with get_db() as db:
        user_data = get_row(db, "users", user.id)
        teams = get_user_teams(db, user.id)

    if not user_data:
        raise HTTPException(status_code=404, detail="User not found")

    return {
        "user": {
            "id": user_data["id"],
            "email": user_data["email"],
            "name": user_data["name"],
            "avatar_url": user_data.get("avatar_url", ""),
            "preferences": user_data.get("preferences", {}),
        },
        "teams": [{"id": t["id"], "name": t["name"], "role": t["member_role"]} for t in teams],
    }


@router.patch("/me/preferences")
async def update_preferences(
    body: PreferencesUpdate,
    user: CurrentUser = Depends(get_current_user),
):
    """Update user preferences (theme, dark mode, etc.)."""
    with get_db() as db:
        user_data = get_row(db, "users", user.id)
        if not user_data:
            raise HTTPException(status_code=404)

        prefs = user_data.get("preferences", {})
        if isinstance(prefs, str):
            import json
            prefs = json.loads(prefs) if prefs else {}

        if body.theme:
            prefs["theme"] = body.theme
        if body.dark_mode is not None:
            prefs["dark_mode"] = body.dark_mode
        if body.density:
            prefs["density"] = body.density

        update_row(db, "users", user.id, {"preferences": prefs})

    return {"preferences": prefs}


# ---------------------------------------------------------------------------
# Team endpoints
# ---------------------------------------------------------------------------

@router.post("/teams", status_code=201)
async def create_team(body: TeamCreate, user: CurrentUser = Depends(get_current_user)):
    """Create a new team."""
    team_id = generate_id()
    with get_db() as db:
        insert_row(db, "teams", {
            "id": team_id,
            "name": body.name,
            "owner_id": user.id,
        })
        insert_row(db, "team_members", {
            "user_id": user.id,
            "team_id": team_id,
            "role": "owner",
        })

    return {"team": {"id": team_id, "name": body.name, "role": "owner"}}


@router.get("/teams")
async def list_teams(user: CurrentUser = Depends(get_current_user)):
    """List teams the current user belongs to."""
    with get_db() as db:
        teams = get_user_teams(db, user.id)
    return {"teams": [{"id": t["id"], "name": t["name"], "role": t["member_role"]} for t in teams]}


@router.get("/teams/{team_id}/members")
async def list_team_members(team_id: str, user: CurrentUser = Depends(get_current_user)):
    """List members of a team."""
    with get_db() as db:
        # Verify membership
        member = db.execute(
            "SELECT role FROM team_members WHERE user_id = ? AND team_id = ?",
            (user.id, team_id),
        ).fetchone()
        if not member:
            raise HTTPException(status_code=403, detail="Not a member of this team")

        members = get_team_members(db, team_id)

    return {"members": members}


@router.post("/teams/{team_id}/invite")
async def invite_member(
    team_id: str,
    body: TeamInvite,
    user: CurrentUser = Depends(get_current_user),
):
    """Invite a user to a team (by email). Must be admin or owner."""
    with get_db() as db:
        # Check caller has admin+ role
        caller = db.execute(
            "SELECT role FROM team_members WHERE user_id = ? AND team_id = ?",
            (user.id, team_id),
        ).fetchone()
        if not caller or caller["role"] not in ("owner", "admin"):
            raise HTTPException(status_code=403, detail="Requires admin role")

        # Find user by email
        invitee = db.execute(
            "SELECT id FROM users WHERE email = ?", (body.email,)
        ).fetchone()
        if not invitee:
            raise HTTPException(status_code=404, detail="User not found")

        # Check not already a member
        existing = db.execute(
            "SELECT 1 FROM team_members WHERE user_id = ? AND team_id = ?",
            (invitee["id"], team_id),
        ).fetchone()
        if existing:
            raise HTTPException(status_code=409, detail="Already a member")

        if body.role not in ("member", "admin"):
            raise HTTPException(status_code=400, detail="Role must be 'member' or 'admin'")

        insert_row(db, "team_members", {
            "user_id": invitee["id"],
            "team_id": team_id,
            "role": body.role,
        })

    return {"message": f"Invited {body.email} as {body.role}"}


@router.post("/teams/{team_id}/switch")
async def switch_team(team_id: str, response: Response, user: CurrentUser = Depends(get_current_user)):
    """Switch the user's active team context."""
    with get_db() as db:
        member = db.execute(
            "SELECT role FROM team_members WHERE user_id = ? AND team_id = ?",
            (user.id, team_id),
        ).fetchone()
        if not member:
            raise HTTPException(status_code=403, detail="Not a member")

        team = get_row(db, "teams", team_id)

    token = create_token({
        "sub": user.id,
        "email": user.email,
        "name": user.name,
        "team_id": team_id,
    })
    response.set_cookie(
        "tars_token", token,
        httponly=True, samesite="lax", max_age=86400 * 7,
    )
    return {"token": token, "team": {"id": team_id, "name": team["name"]}}
