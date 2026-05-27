"""Explain/provenance helpers for Memory Intelligence Core v0.2."""

from __future__ import annotations

import json
from typing import Any


def explain_memory(db: Any, memory_id: str) -> dict:
    """Return a human-readable provenance/status payload for one memory."""
    memory = db.get_memory(memory_id)
    if memory is None:
        return {"error": f"Memory {memory_id} not found"}
    try:
        metadata = json.loads(memory.get("metadata_json") or "{}")
    except json.JSONDecodeError:
        metadata = {}
    audit_trail = db.query_audit(namespace=memory.get("namespace"), limit=20)
    audit_trail = [
        event for event in audit_trail
        if event.get("memory_id") in (None, memory_id)
    ]
    return {
        "memory_id": memory_id,
        "content_preview": memory.get("content_preview", ""),
        "namespace": memory.get("namespace"),
        "status": memory.get("status"),
        "memory_type": memory.get("memory_type"),
        "type_confidence": memory.get("type_confidence"),
        "type_source": memory.get("type_source"),
        "superseded_by": memory.get("superseded_by"),
        "metadata": metadata,
        "interactions": db.get_interactions(memory_id),
        "trust": {
            "ingested_by": memory.get("ingested_by") or "legacy",
            "caller_identity": memory.get("caller_identity") or "unknown",
            "secret_guard_result": memory.get("secret_guard_result") or "legacy",
            "confirmation_count": memory.get("confirmation_count") or 0,
            "forgotten": memory.get("status") == "forgotten",
            "replaced_by": memory.get("superseded_by"),
        },
        "audit_trail": audit_trail,
    }
