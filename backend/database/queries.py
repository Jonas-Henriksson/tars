"""Database query helpers — reusable CRUD and search operations."""
from __future__ import annotations

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from typing import Any


def generate_id() -> str:
    """Generate a short unique ID."""
    return uuid.uuid4().hex[:12]


# Tables that may not have created_at/updated_at columns
# Tables that don't have standard created_at/updated_at columns
_TABLES_WITHOUT_TIMESTAMPS = {"team_members", "telegram_users", "api_keys", "schema_version", "audit_log"}

# Tables that only have created_at (no updated_at)
_TABLES_CREATED_ONLY = {"messages"}


def now_iso() -> str:
    """Current UTC timestamp in ISO format."""
    return datetime.now(timezone.utc).isoformat()


# ---------------------------------------------------------------------------
# Generic CRUD
# ---------------------------------------------------------------------------

def insert_row(
    conn: sqlite3.Connection,
    table: str,
    data: dict[str, Any],
    *,
    id_field: str = "id",
    auto_id: bool = True,
) -> dict[str, Any]:
    """Insert a row and return it as a dict.

    Args:
        auto_id: If True (default), auto-generate an ID if missing.
                 Set to False for tables with composite keys (e.g. team_members).
    """
    if auto_id and id_field not in data:
        data[id_field] = generate_id()
    if table not in _TABLES_WITHOUT_TIMESTAMPS:
        data.setdefault("created_at", now_iso())
        if table not in _TABLES_CREATED_ONLY:
            data.setdefault("updated_at", now_iso())

    # Serialize lists/dicts to JSON strings
    serialized = {}
    for k, v in data.items():
        if isinstance(v, (list, dict)):
            serialized[k] = json.dumps(v)
        else:
            serialized[k] = v

    cols = ", ".join(serialized.keys())
    placeholders = ", ".join("?" for _ in serialized)
    values = list(serialized.values())

    conn.execute(f"INSERT INTO {table} ({cols}) VALUES ({placeholders})", values)
    return data


def update_row(
    conn: sqlite3.Connection,
    table: str,
    row_id: str,
    updates: dict[str, Any],
    *,
    id_field: str = "id",
) -> dict[str, Any] | None:
    """Update a row by ID. Returns updated row or None if not found."""
    if not updates:
        return None

    updates["updated_at"] = now_iso()

    # Serialize lists/dicts
    serialized = {}
    for k, v in updates.items():
        if isinstance(v, (list, dict)):
            serialized[k] = json.dumps(v)
        else:
            serialized[k] = v

    set_clause = ", ".join(f"{k} = ?" for k in serialized)
    values = list(serialized.values()) + [row_id]

    cur = conn.execute(
        f"UPDATE {table} SET {set_clause} WHERE {id_field} = ?", values
    )
    if cur.rowcount == 0:
        return None

    return get_row(conn, table, row_id, id_field=id_field)


def delete_row(
    conn: sqlite3.Connection,
    table: str,
    row_id: str,
    *,
    id_field: str = "id",
) -> bool:
    """Delete a row by ID. Returns True if deleted."""
    cur = conn.execute(f"DELETE FROM {table} WHERE {id_field} = ?", (row_id,))
    return cur.rowcount > 0


def get_row(
    conn: sqlite3.Connection,
    table: str,
    row_id: str,
    *,
    id_field: str = "id",
) -> dict[str, Any] | None:
    """Get a single row by ID."""
    cur = conn.execute(f"SELECT * FROM {table} WHERE {id_field} = ?", (row_id,))
    row = cur.fetchone()
    return _row_to_dict(row) if row else None


def list_rows(
    conn: sqlite3.Connection,
    table: str,
    *,
    filters: dict[str, Any] | None = None,
    order_by: str = "created_at DESC",
    limit: int = 100,
    offset: int = 0,
) -> list[dict[str, Any]]:
    """List rows with optional filters."""
    query = f"SELECT * FROM {table}"
    params: list[Any] = []

    if filters:
        conditions = []
        for k, v in filters.items():
            if v is not None and v != "":
                conditions.append(f"{k} = ?")
                params.append(v)
        if conditions:
            query += " WHERE " + " AND ".join(conditions)

    query += f" ORDER BY {order_by} LIMIT ? OFFSET ?"
    params.extend([limit, offset])

    rows = conn.execute(query, params).fetchall()
    return [_row_to_dict(r) for r in rows]


def count_rows(
    conn: sqlite3.Connection,
    table: str,
    *,
    filters: dict[str, Any] | None = None,
) -> int:
    """Count rows with optional filters."""
    query = f"SELECT COUNT(*) FROM {table}"
    params: list[Any] = []

    if filters:
        conditions = []
        for k, v in filters.items():
            if v is not None and v != "":
                conditions.append(f"{k} = ?")
                params.append(v)
        if conditions:
            query += " WHERE " + " AND ".join(conditions)

    return conn.execute(query, params).fetchone()[0]


# ---------------------------------------------------------------------------
# Full-text search
# ---------------------------------------------------------------------------

def search_memory(
    conn: sqlite3.Connection,
    query: str,
    *,
    scope: str = "",
    owner_id: str = "",
    category: str = "",
    limit: int = 20,
) -> list[dict[str, Any]]:
    """Search memory using FTS5."""
    sql = """
        SELECT m.*, rank
        FROM memory_fts f
        JOIN memory m ON m.rowid = f.rowid
        WHERE memory_fts MATCH ?
    """
    params: list[Any] = [query]

    if scope:
        sql += " AND m.scope = ?"
        params.append(scope)
    if owner_id:
        sql += " AND m.owner_id = ?"
        params.append(owner_id)
    if category:
        sql += " AND m.category = ?"
        params.append(category)

    sql += " ORDER BY rank LIMIT ?"
    params.append(limit)

    rows = conn.execute(sql, params).fetchall()
    return [_row_to_dict(r) for r in rows]


# ---------------------------------------------------------------------------
# User & team queries
# ---------------------------------------------------------------------------

def get_user_teams(conn: sqlite3.Connection, user_id: str) -> list[dict[str, Any]]:
    """Get all teams a user belongs to."""
    rows = conn.execute("""
        SELECT t.*, tm.role as member_role
        FROM teams t
        JOIN team_members tm ON t.id = tm.team_id
        WHERE tm.user_id = ?
        ORDER BY t.name
    """, (user_id,)).fetchall()
    return [_row_to_dict(r) for r in rows]


def get_team_members(conn: sqlite3.Connection, team_id: str) -> list[dict[str, Any]]:
    """Get all members of a team."""
    rows = conn.execute("""
        SELECT u.id, u.email, u.name, u.avatar_url, tm.role, tm.joined_at
        FROM users u
        JOIN team_members tm ON u.id = tm.user_id
        WHERE tm.team_id = ?
        ORDER BY tm.role, u.name
    """, (team_id,)).fetchall()
    return [_row_to_dict(r) for r in rows]


def get_conversation_messages(
    conn: sqlite3.Connection,
    conversation_id: str,
    *,
    limit: int = 50,
    before: str = "",
) -> list[dict[str, Any]]:
    """Get messages for a conversation, newest first."""
    sql = "SELECT * FROM messages WHERE conversation_id = ?"
    params: list[Any] = [conversation_id]

    if before:
        sql += " AND created_at < ?"
        params.append(before)

    sql += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)

    rows = conn.execute(sql, params).fetchall()
    return [_row_to_dict(r) for r in reversed(rows)]  # Return in chronological order


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _row_to_dict(row: sqlite3.Row) -> dict[str, Any]:
    """Convert a sqlite3.Row to a dict, deserializing JSON fields."""
    d = dict(row)
    # Auto-deserialize known JSON fields
    json_fields = {
        "preferences", "settings", "stakeholders", "milestones",
        "acceptance_criteria", "linked_task_ids", "tool_calls",
        "tool_results", "details",
    }
    for field in json_fields:
        if field in d and isinstance(d[field], str):
            try:
                d[field] = json.loads(d[field])
            except (json.JSONDecodeError, TypeError):
                pass
    return d
