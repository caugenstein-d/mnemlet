"""Tests for intelligence schema migrations and storage helpers."""

import json
import sqlite3
from pathlib import Path

import pytest

from mnemlet.storage.sqlite import MnemletDB


INTELLIGENCE_COLUMNS = {
    "memory_type",
    "type_confidence",
    "type_source",
    "superseded_by",
    "content_summary",
}


def test_new_database_has_intelligence_columns(tmp_path: Path) -> None:
    db = MnemletDB(tmp_path / "mnemlet.db")
    try:
        columns = {row[1] for row in db.conn.execute("PRAGMA table_info(memories)").fetchall()}
    finally:
        db.close()

    assert INTELLIGENCE_COLUMNS.issubset(columns)


def test_existing_database_is_migrated_idempotently(tmp_path: Path) -> None:
    db_path = tmp_path / "old.db"
    conn = sqlite3.connect(db_path)
    conn.execute(
        """CREATE TABLE memories (
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
        )"""
    )
    conn.commit()
    conn.close()

    db = MnemletDB(db_path)
    db.close()
    db = MnemletDB(db_path)
    try:
        columns = {row[1] for row in db.conn.execute("PRAGMA table_info(memories)").fetchall()}
    finally:
        db.close()

    assert INTELLIGENCE_COLUMNS.issubset(columns)


def test_memory_status_type_and_metadata_helpers(tmp_path: Path) -> None:
    db = MnemletDB(tmp_path / "mnemlet.db")
    try:
        memory = db.insert_memory(content_preview="The service runs on port 4050", namespace="infra")

        db.update_memory_type(memory["id"], "fact", 0.8, "heuristic", "Service port")
        db.update_memory_metadata(memory["id"], {"supersedes": "old-id", "policy_flags": ["checked"]})
        db.update_memory_status(memory["id"], "superseded", superseded_by="new-id")
        updated = db.get_memory(memory["id"])
    finally:
        db.close()

    assert updated is not None
    assert updated["memory_type"] == "fact"
    assert updated["type_confidence"] == 0.8
    assert updated["type_source"] == "heuristic"
    assert updated["content_summary"] == "Service port"
    assert updated["status"] == "superseded"
    assert updated["superseded_by"] == "new-id"
    metadata = json.loads(updated["metadata_json"])
    assert metadata["supersedes"] == "old-id"
    assert metadata["policy_flags"] == ["checked"]


def test_update_memory_type_rejects_invalid_type(tmp_path: Path) -> None:
    db = MnemletDB(tmp_path / "mnemlet.db")
    try:
        memory = db.insert_memory(content_preview="The service runs on port 4050", namespace="infra")

        with pytest.raises(ValueError, match="invalid memory type: nonsense"):
            db.update_memory_type(memory["id"], "nonsense", 0.5, "heuristic")
    finally:
        db.close()


def test_update_memory_status_preserves_superseded_link_when_not_replaced(tmp_path: Path) -> None:
    db = MnemletDB(tmp_path / "mnemlet.db")
    try:
        memory = db.insert_memory(content_preview="The service runs on port 4050", namespace="infra")

        db.update_memory_status(memory["id"], "superseded", superseded_by="new-id")
        updated = db.update_memory_status(memory["id"], "forgotten")
    finally:
        db.close()

    assert updated is not None
    assert updated["status"] == "forgotten"
    assert updated["superseded_by"] == "new-id"
