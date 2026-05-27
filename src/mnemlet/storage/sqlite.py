"""SQLite database layer for Mnemlet metadata, FTS, and graph storage."""

import json
import sqlite3
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Optional

from mnemlet.constants import MEMORY_STATUSES, MEMORY_TYPES
from mnemlet.security.audit import AuditEvent
from mnemlet.security.namespace_policies import DEFAULT_POLICIES


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

CREATE TABLE IF NOT EXISTS audit_log (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    timestamp TEXT NOT NULL,
    action TEXT NOT NULL,
    memory_id TEXT DEFAULT NULL,
    namespace TEXT NOT NULL,
    caller TEXT NOT NULL,
    caller_identity TEXT DEFAULT NULL,
    result TEXT NOT NULL,
    details_json TEXT DEFAULT '{}'
);

CREATE TABLE IF NOT EXISTS namespace_policies (
    namespace TEXT NOT NULL,
    policy_key TEXT NOT NULL,
    policy_value TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    PRIMARY KEY (namespace, policy_key)
);

CREATE INDEX IF NOT EXISTS idx_memories_namespace ON memories(namespace);
CREATE INDEX IF NOT EXISTS idx_memories_status ON memories(status);
CREATE INDEX IF NOT EXISTS idx_memories_retention ON memories(retention_score);
CREATE INDEX IF NOT EXISTS idx_interactions_memory ON interactions(memory_id);
CREATE INDEX IF NOT EXISTS idx_interactions_agent ON interactions(agent_id);
CREATE INDEX IF NOT EXISTS idx_audit_log_timestamp ON audit_log(timestamp);
CREATE INDEX IF NOT EXISTS idx_audit_log_namespace ON audit_log(namespace);
CREATE INDEX IF NOT EXISTS idx_audit_log_action ON audit_log(action);
CREATE INDEX IF NOT EXISTS idx_audit_log_memory ON audit_log(memory_id);

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


INTELLIGENCE_MEMORY_COLUMNS: dict[str, str] = {
    "memory_type": "TEXT DEFAULT NULL",
    "type_confidence": "REAL DEFAULT NULL",
    "type_source": "TEXT DEFAULT NULL",
    "superseded_by": "TEXT DEFAULT NULL",
    "content_summary": "TEXT DEFAULT NULL",
}


TRUST_MEMORY_COLUMNS: dict[str, str] = {
    "ingested_by": "TEXT DEFAULT NULL",
    "caller_identity": "TEXT DEFAULT NULL",
    "secret_guard_result": "TEXT DEFAULT NULL",
    "confirmation_count": "INTEGER DEFAULT 0",
}


class MnemletDB:
    """SQLite database for Mnemlet.

    Note: This class is NOT thread-safe for writes. Use a single-threaded access pattern
    (which FastAPI's async event loop provides natively). For multi-threaded access,
    instantiate with `MnemletDB(path)`, then set `db._lock = threading.Lock()` and wrap
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
        self._ensure_intelligence_schema()
        self._ensure_trust_schema()
        self._lock = None  # Lock not included by default; add if needed
        self.conn.commit()

    def _list_tables(self) -> list[str]:
        """List all table names (for testing)."""
        rows = self.conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table'"
        ).fetchall()
        return [r[0] for r in rows]

    def _table_columns(self, table_name: str) -> set[str]:
        """Return column names for a SQLite table."""
        rows = self.conn.execute(f"PRAGMA table_info({table_name})").fetchall()
        return {str(row[1]) for row in rows}

    def _ensure_intelligence_schema(self) -> None:
        """Add v0.2 intelligence columns to existing databases idempotently."""
        columns = self._table_columns("memories")
        for column_name, column_sql in INTELLIGENCE_MEMORY_COLUMNS.items():
            if column_name not in columns:
                self.conn.execute(
                    f"ALTER TABLE memories ADD COLUMN {column_name} {column_sql}"
                )
        self.conn.commit()

    def _ensure_trust_schema(self) -> None:
        """Add v0.3 trust columns to existing databases idempotently."""
        columns = self._table_columns("memories")
        for column_name, column_sql in TRUST_MEMORY_COLUMNS.items():
            if column_name not in columns:
                self.conn.execute(
                    f"ALTER TABLE memories ADD COLUMN {column_name} {column_sql}"
                )
        self.conn.commit()

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

    def get_memories_by_ids(self, memory_ids: list[str]) -> dict[str, dict]:
        """Return memories keyed by ID for the provided IDs."""
        if not memory_ids:
            return {}
        bind_marks = ",".join("?" for _ in memory_ids)
        rows = self.conn.execute(
            f"SELECT * FROM memories WHERE id IN ({bind_marks})",
            tuple(memory_ids),
        ).fetchall()
        return {str(row["id"]): dict(row) for row in rows}

    def update_memory_status(
        self,
        memory_id: str,
        status: str,
        superseded_by: str | None = None,
    ) -> dict | None:
        """Update status, preserving existing supersession link when omitted."""
        if status not in MEMORY_STATUSES:
            raise ValueError(f"invalid memory status: {status}")
        self.conn.execute(
            "UPDATE memories SET status = ?, superseded_by = COALESCE(?, superseded_by) WHERE id = ?",
            (status, superseded_by, memory_id),
        )
        self.conn.commit()
        return self.get_memory(memory_id)

    def update_memory_trust(
        self,
        memory_id: str,
        ingested_by: str | None = None,
        caller_identity: str | None = None,
        secret_guard_result: str | None = None,
    ) -> dict | None:
        """Update v0.3 trust fields for a memory."""
        self.conn.execute(
            """UPDATE memories
               SET ingested_by = COALESCE(?, ingested_by),
                   caller_identity = COALESCE(?, caller_identity),
                   secret_guard_result = COALESCE(?, secret_guard_result)
               WHERE id = ?""",
            (ingested_by, caller_identity, secret_guard_result, memory_id),
        )
        self.conn.commit()
        return self.get_memory(memory_id)

    def increment_confirmation_count(self, memory_id: str) -> dict | None:
        """Increment a memory's confirmation count."""
        self.conn.execute(
            """UPDATE memories
               SET confirmation_count = COALESCE(confirmation_count, 0) + 1
               WHERE id = ?""",
            (memory_id,),
        )
        self.conn.commit()
        return self.get_memory(memory_id)

    def update_memory_type(
        self,
        memory_id: str,
        memory_type: str,
        confidence: float,
        source: str,
        summary: str | None = None,
    ) -> dict | None:
        """Update memory type metadata."""
        if memory_type not in MEMORY_TYPES:
            raise ValueError(f"invalid memory type: {memory_type}")
        bounded_confidence = max(0.0, min(1.0, confidence))
        self.conn.execute(
            """UPDATE memories
               SET memory_type = ?, type_confidence = ?, type_source = ?, content_summary = ?
               WHERE id = ?""",
            (memory_type, bounded_confidence, source, summary, memory_id),
        )
        self.conn.commit()
        return self.get_memory(memory_id)

    def update_memory_metadata(self, memory_id: str, updates: dict[str, Any]) -> dict | None:
        """Merge updates into a memory's metadata_json object."""
        memory = self.get_memory(memory_id)
        if memory is None:
            return None
        try:
            metadata = json.loads(memory.get("metadata_json") or "{}")
        except json.JSONDecodeError:
            metadata = {}
        metadata.update(updates)
        self.conn.execute(
            "UPDATE memories SET metadata_json = ? WHERE id = ?",
            (json.dumps(metadata, ensure_ascii=False), memory_id),
        )
        self.conn.commit()
        return self.get_memory(memory_id)

    def record_audit(self, event: AuditEvent) -> dict[str, Any]:
        """Persist an audit event and return the stored row."""
        now = datetime.now(timezone.utc).isoformat()
        self.conn.execute(
            """INSERT INTO audit_log
               (timestamp, action, memory_id, namespace, caller, caller_identity, result, details_json)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                now,
                event.action,
                event.memory_id,
                event.namespace,
                event.caller,
                event.caller_identity,
                event.result,
                json.dumps(event.details, ensure_ascii=False),
            ),
        )
        self.conn.commit()
        row = self.conn.execute("SELECT * FROM audit_log ORDER BY id DESC LIMIT 1").fetchone()
        return self._audit_row_to_dict(row)

    def _audit_row_to_dict(self, row: sqlite3.Row | None) -> dict[str, Any]:
        """Convert an audit row to API shape."""
        if row is None:
            return {}
        item = dict(row)
        try:
            item["details"] = json.loads(item.pop("details_json") or "{}")
        except json.JSONDecodeError:
            item["details"] = {}
        return item

    def query_audit(
        self,
        namespace: str | None = None,
        action: str | None = None,
        since: str | None = None,
        limit: int = 100,
    ) -> list[dict[str, Any]]:
        """Query audit events with optional filters."""
        clauses = []
        params: list[Any] = []
        if namespace:
            clauses.append("namespace = ?")
            params.append(namespace)
        if action:
            clauses.append("action = ?")
            params.append(action)
        if since:
            clauses.append("timestamp >= ?")
            params.append(since)
        where = " WHERE " + " AND ".join(clauses) if clauses else ""
        params.append(max(1, min(limit, 500)))
        rows = self.conn.execute(
            f"SELECT * FROM audit_log{where} ORDER BY timestamp DESC, id DESC LIMIT ?",
            tuple(params),
        ).fetchall()
        return [self._audit_row_to_dict(row) for row in rows]

    def get_namespace_policy(self, namespace: str, key: str) -> str:
        """Return a namespace policy value, falling back to defaults."""
        if key not in DEFAULT_POLICIES:
            raise ValueError(f"unknown namespace policy: {key}")
        row = self.conn.execute(
            "SELECT policy_value FROM namespace_policies WHERE namespace = ? AND policy_key = ?",
            (namespace, key),
        ).fetchone()
        return str(row["policy_value"]) if row else DEFAULT_POLICIES[key]

    def set_namespace_policy(self, namespace: str, key: str, value: str) -> dict[str, str]:
        """Insert or update one namespace policy value."""
        if key not in DEFAULT_POLICIES:
            raise ValueError(f"unknown namespace policy: {key}")
        now = datetime.now(timezone.utc).isoformat()
        self.conn.execute(
            """INSERT INTO namespace_policies (namespace, policy_key, policy_value, updated_at)
               VALUES (?, ?, ?, ?)
               ON CONFLICT(namespace, policy_key) DO UPDATE SET
               policy_value = excluded.policy_value,
               updated_at = excluded.updated_at""",
            (namespace, key, value, now),
        )
        self.conn.commit()
        return {"namespace": namespace, "policy_key": key, "policy_value": value}

    def list_namespace_policies(self, namespace: str) -> dict[str, str]:
        """List effective namespace policies including defaults."""
        policies = dict(DEFAULT_POLICIES)
        rows = self.conn.execute(
            "SELECT policy_key, policy_value FROM namespace_policies WHERE namespace = ?",
            (namespace,),
        ).fetchall()
        for row in rows:
            policies[str(row["policy_key"])] = str(row["policy_value"])
        return policies

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
