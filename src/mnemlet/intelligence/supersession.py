"""Supersession and contradiction handling for Memory Intelligence Core v0.2."""

from __future__ import annotations

import json
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
        if self._has_explicit_supersede(new_memory):
            return []
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
        self._merge_unresolved_flags(old_id, new_id, "supersede_protected")
        self._merge_unresolved_flags(new_id, old_id, "contradiction_unresolved")
        self.db.record_interaction(new_id, "contradiction_detected", agent_id="api")

    def _merge_unresolved_flags(self, target_id: str, other_id: str, flag: str) -> None:
        """Idempotently union ``contradicts_with`` and ``policy_flags`` lists.

        ``update_memory_metadata`` performs a shallow merge that would clobber
        list-valued fields if called multiple times. Reading first and merging
        lets multiple contradictions accumulate against the same memory.
        """
        memory = self.db.get_memory(target_id)
        if memory is None:
            return
        try:
            metadata = json.loads(memory.get("metadata_json") or "{}")
        except json.JSONDecodeError:
            metadata = {}
        contradicts = list(metadata.get("contradicts_with") or [])
        if other_id not in contradicts:
            contradicts.append(other_id)
        flags = list(metadata.get("policy_flags") or [])
        if flag not in flags:
            flags.append(flag)
        self.db.update_memory_metadata(
            target_id,
            {"contradicts_with": contradicts, "policy_flags": flags},
        )

    def _has_explicit_supersede(self, new_memory: dict) -> bool:
        """Return True when the operator already set ``supersede_reason``.

        Manual replace/merge flows pass an explicit ``supersede_reason``. The
        engine must not overwrite that trail with an auto-derived decision.
        """
        raw = new_memory.get("metadata_json")
        if not isinstance(raw, str):
            return False
        try:
            metadata = json.loads(raw or "{}")
        except json.JSONDecodeError:
            return False
        return "supersede_reason" in metadata


class LLMContradictionDetector:
    """Adapter for the existing optional local LLM backend."""

    def __init__(self, llm_backend) -> None:
        self.llm_backend = llm_backend

    def detect(self, new_content: str, existing_content: str) -> ContradictionDecision:
        # Fix 3 / Option A: LLMBackend.detect_contradiction does not return a
        # ``confidence`` field, so default to a usable value when the LLM
        # signals a contradiction. Without this, raw.get("confidence", 0.0)
        # would always be 0.0 and the LLM path could never auto-supersede.
        if not self.llm_backend.available:
            return ContradictionDecision(False, 0.0, "llm unavailable")
        raw = self.llm_backend.detect_contradiction(new_content, existing_content)
        contradiction = bool(raw.get("contradiction", False))
        confidence = float(raw.get("confidence", 0.85 if contradiction else 0.0))
        explanation = str(raw.get("explanation", ""))
        return ContradictionDecision(contradiction, confidence, explanation)
