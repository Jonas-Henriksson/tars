"""Database layer — SQLite with FTS5 for full-text search."""
from backend.database.engine import get_db, init_db

__all__ = ["get_db", "init_db"]
