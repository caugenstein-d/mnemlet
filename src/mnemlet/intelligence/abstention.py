"""Abstention decisions for Memory Intelligence Core v0.2."""

from __future__ import annotations

from mnemlet.constants import CONTEXT_SUPPORTING_SCORE_THRESHOLD


def abstention(reason: str) -> dict[str, str]:
    """Return a stable abstention payload for a reason."""
    suggestions = {
        "no_relevant_memories": "Store or confirm a relevant memory before relying on recall.",
        "low_confidence_matches": "Rephrase the query or store a more specific memory.",
        "all_results_filtered": "Only non-active memories matched this query.",
        "contradictory_results": "Resolve or explain contradictory memories before relying on this context.",
    }
    return {"reason": reason, "suggestion": suggestions[reason]}


def decide_abstention(candidates: list[dict], pack_items: list[dict], policy_flags: list[str]) -> dict[str, str] | None:
    """Return abstention payload when recall results are missing, weak, filtered, or contradictory."""
    if not candidates:
        return abstention("no_relevant_memories")
    highest = max(float(item.get("score", 0.0)) for item in candidates)
    if highest < CONTEXT_SUPPORTING_SCORE_THRESHOLD:
        return abstention("low_confidence_matches")
    if not pack_items:
        return abstention("all_results_filtered")
    if "contradiction_unresolved" in policy_flags:
        return abstention("contradictory_results")
    return None
