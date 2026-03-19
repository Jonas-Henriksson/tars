"""SQLite database engine with connection pooling and migration support."""
from __future__ import annotations

import logging
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

logger = logging.getLogger(__name__)

_DB_PATH = Path(__file__).parent.parent.parent / "tars.db"
_connection: sqlite3.Connection | None = None


def _get_connection() -> sqlite3.Connection:
    """Get or create the singleton database connection."""
    global _connection
    if _connection is None:
        _connection = sqlite3.connect(str(_DB_PATH), check_same_thread=False)
        _connection.row_factory = sqlite3.Row
        _connection.execute("PRAGMA journal_mode=WAL")
        _connection.execute("PRAGMA foreign_keys=ON")
        _connection.execute("PRAGMA busy_timeout=5000")
    return _connection


@contextmanager
def get_db() -> Generator[sqlite3.Connection, None, None]:
    """Context manager for database access with automatic commit/rollback."""
    conn = _get_connection()
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise


def init_db() -> None:
    """Initialize database schema and run migrations."""
    conn = _get_connection()
    cur = conn.cursor()

    # Schema version tracking
    cur.execute("""
        CREATE TABLE IF NOT EXISTS schema_version (
            version INTEGER PRIMARY KEY,
            applied_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    conn.commit()

    # Get current version
    row = cur.execute("SELECT MAX(version) FROM schema_version").fetchone()
    current_version = row[0] if row[0] is not None else 0

    # Run migrations
    for version, migration_fn in sorted(_MIGRATIONS.items()):
        if version > current_version:
            logger.info("Applying migration v%d", version)
            migration_fn(cur)
            cur.execute("INSERT INTO schema_version (version) VALUES (?)", (version,))
            conn.commit()
            logger.info("Migration v%d applied", version)

    logger.info("Database initialized at v%d", max(_MIGRATIONS.keys()) if _MIGRATIONS else 0)


# ---------------------------------------------------------------------------
# Migrations
# ---------------------------------------------------------------------------

def _migration_v1(cur: sqlite3.Cursor) -> None:
    """v1: Core tables — users, teams, conversations, messages, memory."""

    # Users
    cur.execute("""
        CREATE TABLE IF NOT EXISTS users (
            id TEXT PRIMARY KEY,
            email TEXT UNIQUE,
            name TEXT NOT NULL,
            password_hash TEXT,
            avatar_url TEXT DEFAULT '',
            preferences TEXT DEFAULT '{}',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            last_login_at TEXT
        )
    """)

    # Teams
    cur.execute("""
        CREATE TABLE IF NOT EXISTS teams (
            id TEXT PRIMARY KEY,
            name TEXT NOT NULL,
            owner_id TEXT NOT NULL REFERENCES users(id),
            settings TEXT DEFAULT '{}',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)

    # Team members
    cur.execute("""
        CREATE TABLE IF NOT EXISTS team_members (
            user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            team_id TEXT NOT NULL REFERENCES teams(id) ON DELETE CASCADE,
            role TEXT NOT NULL DEFAULT 'member' CHECK(role IN ('owner', 'admin', 'member')),
            joined_at TEXT NOT NULL DEFAULT (datetime('now')),
            PRIMARY KEY (user_id, team_id)
        )
    """)

    # Conversations
    cur.execute("""
        CREATE TABLE IF NOT EXISTS conversations (
            id TEXT PRIMARY KEY,
            user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            team_id TEXT REFERENCES teams(id) ON DELETE SET NULL,
            channel TEXT NOT NULL DEFAULT 'web' CHECK(channel IN ('web', 'telegram', 'cli', 'voice')),
            title TEXT DEFAULT '',
            is_archived INTEGER DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_conversations_user ON conversations(user_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_conversations_team ON conversations(team_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_conversations_user_active ON conversations(user_id, is_archived)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_conversations_updated ON conversations(updated_at)")

    # Messages
    cur.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id TEXT PRIMARY KEY,
            conversation_id TEXT NOT NULL REFERENCES conversations(id) ON DELETE CASCADE,
            role TEXT NOT NULL CHECK(role IN ('user', 'assistant', 'system', 'tool')),
            content TEXT NOT NULL,
            tool_calls TEXT,
            tool_results TEXT,
            model TEXT DEFAULT '',
            tokens_used INTEGER DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_messages_conversation ON messages(conversation_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_messages_created ON messages(created_at)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_messages_conv_created ON messages(conversation_id, created_at)")

    # Memory — key-value store with user/team scoping
    cur.execute("""
        CREATE TABLE IF NOT EXISTS memory (
            id TEXT PRIMARY KEY,
            scope TEXT NOT NULL CHECK(scope IN ('user', 'team', 'global')),
            owner_id TEXT NOT NULL,
            category TEXT NOT NULL DEFAULT 'general',
            key TEXT NOT NULL,
            value TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE(scope, owner_id, category, key)
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_memory_scope ON memory(scope, owner_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_memory_category ON memory(category)")

    # FTS5 for semantic search over memory
    cur.execute("""
        CREATE VIRTUAL TABLE IF NOT EXISTS memory_fts USING fts5(
            key, value, category,
            content='memory',
            content_rowid='rowid'
        )
    """)

    # Triggers to keep FTS in sync
    cur.execute("""
        CREATE TRIGGER IF NOT EXISTS memory_ai AFTER INSERT ON memory BEGIN
            INSERT INTO memory_fts(rowid, key, value, category)
            VALUES (new.rowid, new.key, new.value, new.category);
        END
    """)
    cur.execute("""
        CREATE TRIGGER IF NOT EXISTS memory_ad AFTER DELETE ON memory BEGIN
            INSERT INTO memory_fts(memory_fts, rowid, key, value, category)
            VALUES ('delete', old.rowid, old.key, old.value, old.category);
        END
    """)
    cur.execute("""
        CREATE TRIGGER IF NOT EXISTS memory_au AFTER UPDATE ON memory BEGIN
            INSERT INTO memory_fts(memory_fts, rowid, key, value, category)
            VALUES ('delete', old.rowid, old.key, old.value, old.category);
            INSERT INTO memory_fts(rowid, key, value, category)
            VALUES (new.rowid, new.key, new.value, new.category);
        END
    """)


def _migration_v2(cur: sqlite3.Cursor) -> None:
    """v2: Smart tasks, decisions, initiatives, epics — all in SQLite."""

    # Smart tasks (replaces notion_intel.json smart_tasks)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS smart_tasks (
            id TEXT PRIMARY KEY,
            team_id TEXT DEFAULT NULL REFERENCES teams(id) ON DELETE CASCADE,
            description TEXT NOT NULL,
            owner TEXT DEFAULT '',
            status TEXT DEFAULT 'open' CHECK(status IN ('open', 'done')),
            quadrant INTEGER DEFAULT 4 CHECK(quadrant BETWEEN 1 AND 4),
            topic TEXT DEFAULT '',
            follow_up_date TEXT DEFAULT '',
            source_page_id TEXT DEFAULT '',
            source_context TEXT DEFAULT '',
            steps TEXT DEFAULT '',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_smart_tasks_owner ON smart_tasks(owner)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_smart_tasks_status ON smart_tasks(status)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_smart_tasks_team ON smart_tasks(team_id)")

    # Decisions (replaces decisions.json)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS decisions (
            id TEXT PRIMARY KEY,
            team_id TEXT DEFAULT NULL REFERENCES teams(id) ON DELETE CASCADE,
            title TEXT NOT NULL,
            rationale TEXT DEFAULT '',
            decided_by TEXT DEFAULT '',
            stakeholders TEXT DEFAULT '[]',
            context TEXT DEFAULT '',
            initiative_id TEXT DEFAULT '',
            status TEXT DEFAULT 'decided' CHECK(status IN ('decided', 'pending', 'revisit')),
            outcome_notes TEXT DEFAULT '',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_decisions_status ON decisions(status)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_decisions_team ON decisions(team_id)")

    # Initiatives (replaces initiatives.json)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS initiatives (
            id TEXT PRIMARY KEY,
            team_id TEXT DEFAULT NULL REFERENCES teams(id) ON DELETE CASCADE,
            title TEXT NOT NULL,
            description TEXT DEFAULT '',
            owner TEXT DEFAULT '',
            quarter TEXT DEFAULT '',
            status TEXT DEFAULT 'on_track'
                CHECK(status IN ('on_track', 'at_risk', 'off_track', 'completed', 'paused')),
            priority TEXT DEFAULT 'high' CHECK(priority IN ('high', 'medium', 'low')),
            milestones TEXT DEFAULT '[]',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_initiatives_status ON initiatives(status)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_initiatives_team ON initiatives(team_id)")

    # Key results (OKRs linked to initiatives)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS key_results (
            id TEXT PRIMARY KEY,
            initiative_id TEXT NOT NULL REFERENCES initiatives(id) ON DELETE CASCADE,
            description TEXT NOT NULL,
            target TEXT DEFAULT '',
            current TEXT DEFAULT '',
            owner TEXT DEFAULT '',
            status TEXT DEFAULT 'in_progress'
                CHECK(status IN ('in_progress', 'achieved', 'missed')),
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_kr_initiative ON key_results(initiative_id)")

    # Epics (replaces epics.json)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS epics (
            id TEXT PRIMARY KEY,
            team_id TEXT DEFAULT NULL REFERENCES teams(id) ON DELETE CASCADE,
            initiative_id TEXT DEFAULT NULL REFERENCES initiatives(id) ON DELETE SET NULL,
            title TEXT NOT NULL,
            description TEXT DEFAULT '',
            owner TEXT DEFAULT '',
            status TEXT DEFAULT 'backlog'
                CHECK(status IN ('backlog', 'in_progress', 'done', 'cancelled')),
            priority TEXT DEFAULT 'high' CHECK(priority IN ('high', 'medium', 'low')),
            quarter TEXT DEFAULT '',
            acceptance_criteria TEXT DEFAULT '[]',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_epics_status ON epics(status)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_epics_team ON epics(team_id)")

    # User stories
    cur.execute("""
        CREATE TABLE IF NOT EXISTS stories (
            id TEXT PRIMARY KEY,
            epic_id TEXT NOT NULL REFERENCES epics(id) ON DELETE CASCADE,
            title TEXT NOT NULL,
            description TEXT DEFAULT '',
            owner TEXT DEFAULT '',
            status TEXT DEFAULT 'backlog'
                CHECK(status IN ('backlog', 'ready', 'in_progress', 'in_review', 'done', 'blocked')),
            priority TEXT DEFAULT 'medium' CHECK(priority IN ('high', 'medium', 'low')),
            size TEXT DEFAULT 'M' CHECK(size IN ('XS', 'S', 'M', 'L', 'XL')),
            acceptance_criteria TEXT DEFAULT '[]',
            linked_task_ids TEXT DEFAULT '[]',
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_stories_epic ON stories(epic_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_stories_status ON stories(status)")

    # People profiles (replaces people_profiles.json)
    cur.execute("""
        CREATE TABLE IF NOT EXISTS people (
            id TEXT PRIMARY KEY,
            team_id TEXT DEFAULT NULL REFERENCES teams(id) ON DELETE CASCADE,
            name TEXT NOT NULL,
            role TEXT DEFAULT '',
            relationship TEXT DEFAULT '',
            organization TEXT DEFAULT '',
            email TEXT DEFAULT '',
            notes TEXT DEFAULT '',
            manually_added INTEGER DEFAULT 0,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            updated_at TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE(team_id, name)
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_people_team ON people(team_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_people_name ON people(name)")


def _migration_v3(cur: sqlite3.Cursor) -> None:
    """v3: Telegram user mapping and API keys."""

    # Telegram user to TARS user mapping
    cur.execute("""
        CREATE TABLE IF NOT EXISTS telegram_users (
            telegram_id INTEGER PRIMARY KEY,
            user_id TEXT NOT NULL REFERENCES users(id) ON DELETE CASCADE,
            username TEXT DEFAULT '',
            linked_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)

    # API keys — team-level or user-level
    cur.execute("""
        CREATE TABLE IF NOT EXISTS api_keys (
            id TEXT PRIMARY KEY,
            scope TEXT NOT NULL CHECK(scope IN ('user', 'team')),
            owner_id TEXT NOT NULL,
            service TEXT NOT NULL,
            key_name TEXT NOT NULL,
            encrypted_value TEXT NOT NULL,
            created_at TEXT NOT NULL DEFAULT (datetime('now')),
            UNIQUE(scope, owner_id, service, key_name)
        )
    """)

    # Audit log
    cur.execute("""
        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id TEXT,
            team_id TEXT,
            action TEXT NOT NULL,
            entity_type TEXT DEFAULT '',
            entity_id TEXT DEFAULT '',
            details TEXT DEFAULT '{}',
            created_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
    """)
    cur.execute("CREATE INDEX IF NOT EXISTS idx_audit_user ON audit_log(user_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_audit_team ON audit_log(team_id)")
    cur.execute("CREATE INDEX IF NOT EXISTS idx_audit_created ON audit_log(created_at)")


_MIGRATIONS = {
    1: _migration_v1,
    2: _migration_v2,
    3: _migration_v3,
}
