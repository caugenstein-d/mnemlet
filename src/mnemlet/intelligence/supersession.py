"""Supersession and contradiction handling for Memory Intelligence Core v0.2."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from mnemlet.constants import CONTRADICTION_AUTO_SUPERSEDE_THRESHOLD, MEMORY_STATUS_SUPERSEDED
from mnemlet.intelligence.policy import can_auto_supersede


@dataclass(frozen=True)
class ContradictionDecision:
    """Decision returned by a contradiction detector."""

    contradiction: bool
    confidence: float
    explanation: str


class ContradictionDetector(Protocol):
    """Protocol for local or fake contradiction detectors."""

    def detect(self, new_content: str, existing_content: str) -> ContradictionDecision:
        """Compare two memories and return a contradiction decision."""


class SupersessionEngine:
    """Apply soft supersession decisions for newly ingested memories."""

    def __init__(self, db, detector: ContradictionDetector, candidate_limit: int = 3) -> None:
        self.db = db
        self.detector = detector
        self.candidate_limit = candidate_limit

    def process_new_memory(self, new_memory: dict, new_content: str) -> list[str]:
        """Check active same-namespace candidates and supersede or flag contradictions."""
        candidates = self._active_candidates(new_memory)
        superseded_ids: list[str] = []
        for candidate in candidates:
            decision = self.detector.detect(new_content, candidate["content_preview"])
            if not decision.contradiction:
                continue
            if (
                decision.confidence >= CONTRADICTION_AUTO_SUPERSEDE_THRESHOLD
                and can_auto_supersede(candidate.get("memory_type"))
                and can_auto_supersede(new_memory.get("memory_type"))
            ):
                self.db.update_memory_status(candidate["id"], MEMORY_STATUS_SUPERSEDED, superseded_by=new_memory["id"])
                self.db.update_memory_metadata(
                    new_memory["id"],
                    {"supersedes": candidate["id"], "supersede_reason": "contradiction"},
                )
                self.db.record_interaction(candidate["id"], "supersede", agent_id="api")
                superseded_ids.append(candidate["id"])
            else:
                self._flag_unresolved(candidate["id"], new_memory["id"])
        return superseded_ids

    def _active_candidates(self, new_memory: dict) -> list[dict]:
        rows = self.db.conn.execute(
            """SELECT * FROM memories
               WHERE namespace = ? AND status = 'active' AND id != ?
               ORDER BY created_at DESC LIMIT ?""",
            (new_memory["namespace"], new_memory["id"], self.candidate_limit),
        ).fetchall()
        return [dict(row) for row in rows]

    def _flag_unresolved(self, old_id: str, new_id: str) -> None:
        self.db.update_memory_metadata(
            old_id,
            {"contradicts_with": [new_id], "policy_flags": ["supersede_protected"]},
        )
        self.db.update_memory_metadata(
            new_id,
            {"contradicts_with": [old_id], "policy_flags": ["contradiction_unresolved"]},
        )
        self.db.record_interaction(new_id, "contradiction_detected", agent_id="api")


class LLMContradictionDetector:
    """Adapter for the existing optional local LLM backend."""

    def __init__(self, llm_backend) -> None:
        self.llm_backend = llm_backend

    def detect(self, new_content: str, existing_content: str) -> ContradictionDecision:
        if not self.llm_backend.available:
            return ContradictionDecision(False, 0.0, "llm unavailable")
        raw = self.llm_backend.detect_contradiction(new_content, existing_content)
        return ContradictionDecision(
            bool(raw.get("contradiction", False)),
            float(raw.get("confidence", 0.0)),
            str(raw.get("explanation", "")),
        )
