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
    }
