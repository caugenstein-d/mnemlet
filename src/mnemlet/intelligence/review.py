"""Manual review commands for Memory Intelligence Core v0.2."""

from __future__ import annotations

from typing import Any

from mnemlet.constants import BOOST_CONFIRM, MEMORY_STATUS_FORGOTTEN, MEMORY_STATUS_SUPERSEDED
from mnemlet.security.namespace_policies import policy_value_bool


class ReviewService:
    """Implements remember, forget, replace, and confirm operations."""

    def __init__(self, db: Any, ingest_engine: Any) -> None:
        self.db = db
        self.ingest_engine = ingest_engine

    def remember(
        self,
        content: str,
        namespace: str = "default",
        importance: float = 0.5,
        memory_type: str | None = None,
    ) -> dict:
        """Store a memory deliberately, bypassing duplicate suppression."""
        return self.ingest_engine.ingest(
            content=content,
            namespace=namespace,
            importance=importance,
            metadata={},
            dedup=False,
            memory_type=memory_type,
            type_source="manual" if memory_type else None,
        )

    def forget(self, memory_id: str, confirm: bool = False) -> dict:
        """Mark a memory as forgotten without deleting it."""
        existing = self.db.get_memory(memory_id)
        if existing is None:
            return {"error": f"Memory {memory_id} not found"}
        requires_confirmation = policy_value_bool(
            self.db.get_namespace_policy(existing["namespace"], "confirm_before_forget")
        )
        if requires_confirmation and not confirm:
            return {"error": "confirm=true required", "requires_confirmation": True}
        memory = self.db.update_memory_status(memory_id, MEMORY_STATUS_FORGOTTEN)
        self.db.record_interaction(memory_id, "forget", agent_id="api")
        return self.db.get_memory(memory_id)

    def replace(self, memory_id: str, new_content: str, importance: float = 0.5) -> dict:
        """Supersede an old memory with a new active memory."""
        old = self.db.get_memory(memory_id)
        if old is None:
            return {"error": f"Memory {memory_id} not found"}
        result = self.ingest_engine.ingest(
            content=new_content,
            namespace=old["namespace"],
            importance=importance,
            metadata={"supersedes": memory_id, "supersede_reason": "replace"},
            dedup=False,
            memory_type=old.get("memory_type"),
            type_source="manual" if old.get("memory_type") else None,
        )
        new_id = str(result["memory_id"])
        self.db.update_memory_status(memory_id, MEMORY_STATUS_SUPERSEDED, superseded_by=new_id)
        self.db.record_interaction(memory_id, "replace", agent_id="api")
        return {
            "old_id": memory_id,
            "new_id": new_id,
            "old_status": MEMORY_STATUS_SUPERSEDED,
            "new_memory": self.db.get_memory(new_id),
        }

    def confirm(self, memory_id: str) -> dict:
        """Boost retention score and record confirmation."""
        memory = self.db.get_memory(memory_id)
        if memory is None:
            return {"error": f"Memory {memory_id} not found"}
        new_score = min(1.0, float(memory["retention_score"]) + BOOST_CONFIRM)
        self.db.update_score(memory_id, new_score)
        self.db.increment_confirmation_count(memory_id)
        self.db.record_interaction(memory_id, "confirm", agent_id="api")
        return self.db.get_memory(memory_id)
