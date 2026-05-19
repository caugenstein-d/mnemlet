"""SQLite database layer for Engram metadata, FTS, and graph storage."""

import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional


SCHEMA = """
CREATE TABLE IF NOT EXISTS memories (
    id TEXT PRIMARY KEY,
    namespace TEXT NOT NULL,
    content_hash TEXT NOT NULL DEFAULT '',
    content_preview TEXT NOT NULL,
    chunk_count INTEGER DEFAULT 1,
    retention_score REAL DEFAULT 0.5,
    importance REAL DEFAULT 0.5,
    created_at TEXT NOT NULL,
    last_accessed_at TEXT NOT NULL,
    access_count INTEGER DEFAULT 0,
    metadata_json TEXT DEFAULT '{}',
    status TEXT DEFAULT 'active'
);

CREATE TABLE IF NOT EXISTS interactions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    memory_id TEXT NOT NULL,
    interaction_type TEXT NOT NULL,
    agent_id TEXT NOT NULL,
    timestamp TEXT NOT NULL,
    FOREIGN KEY (memory_id) REFERENCES memories(id)
);

CREATE TABLE IF NOT EXISTS decay_configs (
    namespace TEXT PRIMARY KEY,
    lambda REAL NOT NULL DEFAULT 0.01,
    purge_threshold REAL DEFAULT 0.05,
    hard_delete_threshold REAL DEFAULT 0.01,
    hard_delete_age_days INTEGER DEFAULT 90,
    updated_at TEXT NOT NULL
);

CREATE VIRTUAL TABLE IF NOT EXISTS memories_fts USING fts5(
    content_preview,
    namespace,
    metadata_json,
    content='memories',
    content_rowid='rowid'
);

CREATE TABLE IF NOT EXISTS graph_edges (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    source_entity TEXT NOT NULL,
    relation TEXT NOT NULL,
    target_entity TEXT NOT NULL,
    created_at TEXT NOT NULL,
    metadata_json TEXT DEFAULT '{}'
);

CREATE INDEX IF NOT EXISTS idx_memories_namespace ON memories(namespace);
CREATE INDEX IF NOT EXISTS idx_memories_status ON memories(status);
CREATE INDEX IF NOT EXISTS idx_memories_retention ON memories(retention_score);
CREATE INDEX IF NOT EXISTS idx_interactions_memory ON interactions(memory_id);
CREATE INDEX IF NOT EXISTS idx_interactions_agent ON interactions(agent_id);

CREATE TRIGGER IF NOT EXISTS memories_fts_insert AFTER INSERT ON memories BEGIN
    INSERT INTO memories_fts(rowid, content_preview, namespace, metadata_json)
    VALUES (new.rowid, new.content_preview, new.namespace, new.metadata_json);
END;

CREATE TRIGGER IF NOT EXISTS memories_fts_delete AFTER DELETE ON memories BEGIN
    INSERT INTO memories_fts(memories_fts, rowid, content_preview, namespace, metadata_json)
    VALUES ('delete', old.rowid, old.content_preview, old.namespace, old.metadata_json);
END;

CREATE TRIGGER IF NOT EXISTS memories_fts_update AFTER UPDATE ON memories BEGIN
    INSERT INTO memories_fts(memories_fts, rowid, content_preview, namespace, metadata_json)
    VALUES ('delete', old.rowid, old.content_preview, old.namespace, old.metadata_json);
    INSERT INTO memories_fts(rowid, content_preview, namespace, metadata_json)
    VALUES (new.rowid, new.content_preview, new.namespace, new.metadata_json);
END;
"""


class EngramDB:
    """SQLite database for Engram.

    Note: This class is NOT thread-safe for writes. Use a single-threaded access pattern
    (which FastAPI's async event loop provides natively). For multi-threaded access,
    instantiate with `EngramDB(path)`, then set `db._lock = threading.Lock()` and wrap
    write operations.
    """

    def __init__(self, db_path: Path):
        self.db_path = db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)
        # check_same_thread=False is required for FastAPI async handlers.
        # WAL mode allows concurrent reads safely. Write serialization is
        # handled by FastAPI's single-threaded async event loop.
        self.conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA foreign_keys=ON")
        self.conn.executescript(SCHEMA)
        self._lock = None  # Lock not included by default; add if needed
        self.conn.commit()

    def _list_tables(self) -> list[str]:
        """List all table names (for testing)."""
        rows = self.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        return [r[0] for r in rows]

    def close(self):
        """Close the database connection."""
        if self.conn:
            self.conn.close()
            self.conn = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False

    def insert_memory(
        self,
        memory_id: Optional[str] = None,
        namespace: str = "default",
        content_preview: str = "",
        content_hash: str = "",
        importance: float = 0.5,
        metadata: Optional[dict] = None,
    ) -> dict:
        """Insert a new memory and return its row as dict."""
        import json
        mid = memory_id or str(uuid.uuid4())
        now = datetime.now(timezone.utc).isoformat()
        score = importance * 0.5

        self.conn.execute(
            """INSERT INTO memories (id, namespace, content_hash, content_preview,
               retention_score, importance, created_at, last_accessed_at, metadata_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (mid, namespace, content_hash, content_preview, score, importance,
             now, now, json.dumps(metadata or {})),
        )
        self.conn.commit()
        result = self.get_memory(mid)
        if result is None:
            raise RuntimeError(f"Memory {mid} not found after insert")
        return dict(result)

    def get_memory(self, memory_id: str) -> Optional[dict]:
        """Retrieve a memory by ID."""
        row = self.conn.execute(
            "SELECT * FROM memories WHERE id = ?", (memory_id,)
        ).fetchone()
        return dict(row) if row else None

    def _sanitize_fts_query(self, query: str) -> str:
        """Sanitize user input for FTS5 MATCH queries.
        
        Wraps the query in double quotes to prevent FTS5 syntax characters
        (*, -, AND, OR, NEAR) from being interpreted as operators.
        """
        safe = query.replace('"', '""')
        return f'"{safe}"'

    def search_fts(self, query: str, namespace: Optional[str] = None, limit: int = 5) -> list[dict]:
        """Full-text search using FTS5."""
        if namespace:
            rows = self.conn.execute(
                """SELECT memories.id, memories.namespace, memories.content_preview,
                   memories.retention_score, memories.created_at
                   FROM memories_fts
                   JOIN memories ON memories_fts.rowid = memories.rowid
                   WHERE memories_fts MATCH ? AND memories.namespace = ?
                   ORDER BY rank LIMIT ?""",
                (self._sanitize_fts_query(query), namespace, limit),
            ).fetchall()
        else:
            rows = self.conn.execute(
                """SELECT memories.id, memories.namespace, memories.content_preview,
                   memories.retention_score, memories.created_at
                   FROM memories_fts
                   JOIN memories ON memories_fts.rowid = memories.rowid
                   WHERE memories_fts MATCH ?
                   ORDER BY rank LIMIT ?""",
                (self._sanitize_fts_query(query), limit),
            ).fetchall()
        return [dict(r) for r in rows]

    def update_score(self, memory_id: str, score: float) -> None:
        """Update the retention score of a memory."""
        self.conn.execute(
            "UPDATE memories SET retention_score = ? WHERE id = ?",
            (score, memory_id),
        )
        self.conn.commit()

    def record_interaction(self, memory_id: str, interaction_type: str, agent_id: str) -> None:
        """Record an interaction event."""
        now = datetime.now(timezone.utc).isoformat()
        self.conn.execute(
            """INSERT INTO interactions (memory_id, interaction_type, agent_id, timestamp)
               VALUES (?, ?, ?, ?)""",
            (memory_id, interaction_type, agent_id, now),
        )
        self.conn.execute(
            """UPDATE memories
               SET last_accessed_at = ?, access_count = access_count + 1
               WHERE id = ?""",
            (now, memory_id),
        )
        self.conn.commit()

    def get_interactions(self, memory_id: str, limit: int = 10) -> list[dict]:
        """Get recent interactions for a memory."""
        rows = self.conn.execute(
            "SELECT * FROM interactions WHERE memory_id = ? ORDER BY timestamp DESC LIMIT ?",
            (memory_id, limit),
        ).fetchall()
        return [dict(r) for r in rows]

    def get_decay_config(self, namespace: str) -> Optional[dict]:
        """Get decay config for a namespace, or None."""
        row = self.conn.execute(
            "SELECT * FROM decay_configs WHERE namespace = ?", (namespace,)
        ).fetchone()
        return dict(row) if row else None

    def set_decay_config(
        self, namespace: str, lambda_: float = 0.01,
        purge_threshold: float = 0.05, hard_delete_threshold: float = 0.01,
        hard_delete_age_days: int = 90,
    ) -> dict:
        """Insert or update decay config for a namespace."""
        now = datetime.now(timezone.utc).isoformat()
        self.conn.execute(
            """INSERT INTO decay_configs (namespace, lambda, purge_threshold,
               hard_delete_threshold, hard_delete_age_days, updated_at)
               VALUES (?, ?, ?, ?, ?, ?)
               ON CONFLICT(namespace) DO UPDATE SET
               lambda = excluded.lambda,
               purge_threshold = excluded.purge_threshold,
               hard_delete_threshold = excluded.hard_delete_threshold,
               hard_delete_age_days = excluded.hard_delete_age_days,
               updated_at = excluded.updated_at""",
            (namespace, lambda_, purge_threshold, hard_delete_threshold, hard_delete_age_days, now),
        )
        self.conn.commit()
        return dict(self.get_decay_config(namespace))

    def get_active_memories_for_decay(self, limit: int = 1000) -> list[dict]:
        """Get active memories that need decay processing, ordered by last_accessed_at ASC."""
        rows = self.conn.execute(
            """SELECT id, namespace, retention_score, last_accessed_at
               FROM memories WHERE status = 'active'
               ORDER BY last_accessed_at ASC LIMIT ?""",
            (limit,),
        ).fetchall()
        return [dict(r) for r in rows]
