"""SQLite database layer for Memoria metadata, FTS, and graph storage."""

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


class MemoriaDB:
    """SQLite database for Memoria."""

    def __init__(self, db_path: Path):
        self.db_path = db_path
        db_path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(str(db_path), check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode=WAL")
        self.conn.execute("PRAGMA foreign_keys=ON")
        self.conn.executescript(SCHEMA)
        self.conn.commit()

    def _list_tables(self) -> list[str]:
        """List all table names (for testing)."""
        rows = self.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        return [r[0] for r in rows]

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
        return dict(self.get_memory(mid))

    def get_memory(self, memory_id: str) -> Optional[dict]:
        """Retrieve a memory by ID."""
        row = self.conn.execute(
            "SELECT * FROM memories WHERE id = ?", (memory_id,)
        ).fetchone()
        return dict(row) if row else None

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
                (query, namespace, limit),
            ).fetchall()
        else:
            rows = self.conn.execute(
                """SELECT memories.id, memories.namespace, memories.content_preview,
                   memories.retention_score, memories.created_at
                   FROM memories_fts
                   JOIN memories ON memories_fts.rowid = memories.rowid
                   WHERE memories_fts MATCH ?
                   ORDER BY rank LIMIT ?""",
                (query, limit),
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
