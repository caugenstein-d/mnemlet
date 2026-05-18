"""Tests for SQLite storage layer."""

import pytest
import tempfile
from pathlib import Path
from memoria.storage.sqlite import MemoriaDB


@pytest.fixture
def db():
    """Create a temporary database for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test.db"
        database = MemoriaDB(db_path)
        yield database


def test_schema_creation(db):
    """Tables are created on init."""
    tables = db._list_tables()
    assert "memories" in tables
    assert "interactions" in tables
    assert "decay_configs" in tables
    assert "memories_fts" in tables


def test_insert_memory(db):
    """A memory can be inserted and retrieved."""
    memory = db.insert_memory(
        memory_id="test-1",
        namespace="test/global",
        content_preview="User prefers dark mode",
        importance=0.9,
    )
    assert memory["retention_score"] == 0.45  # importance * 0.5
    assert memory["status"] == "active"
    assert memory["namespace"] == "test/global"


def test_get_memory(db):
    """A stored memory can be retrieved by ID."""
    db.insert_memory(memory_id="test-2", namespace="test/global", content_preview="Hello world")
    result = db.get_memory("test-2")
    assert result is not None
    assert result["content_preview"] == "Hello world"


def test_get_memory_not_found(db):
    """Returns None for unknown ID."""
    assert db.get_memory("nonexistent") is None


def test_ftsearch(db):
    """FTS5 text search finds matching content."""
    db.insert_memory(memory_id="a", namespace="test", content_preview="dark mode preference")
    db.insert_memory(memory_id="b", namespace="test", content_preview="code formatting rules")
    db.insert_memory(memory_id="c", namespace="test", content_preview="preferences for editor theme")
    results = db.search_fts("preferences", namespace="test", limit=5)
    assert len(results) >= 1
    assert "c" in [r["id"] for r in results]


def test_ftsearch_namespace_isolation(db):
    """FTS search respects namespace boundaries."""
    db.insert_memory(memory_id="x", namespace="ns1", content_preview="shared fact")
    db.insert_memory(memory_id="y", namespace="ns2", content_preview="shared fact")
    results = db.search_fts("shared", namespace="ns1", limit=5)
    assert len(results) == 1
    assert results[0]["id"] == "x"


def test_update_retention_score(db):
    """Retention score can be updated."""
    db.insert_memory(memory_id="u", namespace="test", content_preview="update me")
    db.update_score("u", 0.75)
    result = db.get_memory("u")
    assert result["retention_score"] == 0.75


def test_record_interaction(db):
    """Interaction events are recorded."""
    db.insert_memory(memory_id="i", namespace="test", content_preview="interact me")
    db.record_interaction("i", "recall", "claude-code")
    interactions = db.get_interactions("i", limit=10)
    assert len(interactions) == 1
    assert interactions[0]["interaction_type"] == "recall"
    assert interactions[0]["agent_id"] == "claude-code"
