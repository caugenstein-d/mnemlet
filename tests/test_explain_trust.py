"""Tests for v0.3 Explain+ trust fields."""

from __future__ import annotations

from pathlib import Path

from mnemlet.intelligence.provenance import explain_memory
from mnemlet.security.audit import AuditEvent
from mnemlet.storage.sqlite import MnemletDB


def test_trust_columns_are_added_to_existing_schema(tmp_path: Path) -> None:
    db = MnemletDB(tmp_path / "mnemlet.db")
    try:
        columns = db._table_columns("memories")
    finally:
        db.close()

    assert {
        "ingested_by",
        "caller_identity",
        "secret_guard_result",
        "confirmation_count",
    }.issubset(columns)


def test_explain_includes_trust_block_and_audit_trail(tmp_path: Path) -> None:
    db = MnemletDB(tmp_path / "mnemlet.db")
    try:
        memory = db.insert_memory(
            namespace="preferences",
            content_preview="Christoph prefers dark mode",
        )
        db.update_memory_trust(
            memory["id"],
            ingested_by="rest",
            caller_identity="abc12345",
            secret_guard_result="clean",
        )
        db.increment_confirmation_count(memory["id"])
        db.record_audit(
            AuditEvent(
                action="ingest",
                memory_id=memory["id"],
                namespace="preferences",
                caller="rest",
                caller_identity=None,
                result="success",
                details={},
            )
        )

        result = explain_memory(db, memory["id"])
    finally:
        db.close()

    assert result["trust"]["ingested_by"] == "rest"
    assert result["trust"]["caller_identity"] == "abc12345"
    assert result["trust"]["secret_guard_result"] == "clean"
    assert result["trust"]["confirmation_count"] == 1
    assert result["audit_trail"][0]["action"] == "ingest"
