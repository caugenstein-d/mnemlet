"""Context Pack assembly for agent-friendly memory recall."""

from __future__ import annotations

import json
from typing import Any

from mnemlet.constants import (
    CONTEXT_PRIMARY_SCORE_THRESHOLD,
    CONTEXT_SUPPORTING_SCORE_THRESHOLD,
    MEMORY_STATUS_ACTIVE,
    MEMORY_STATUS_SUPERSEDED,
)
from mnemlet.intelligence.abstention import decide_abstention


def build_context_pack(
    query: str,
    results: list[dict[str, Any]],
    include_superseded: bool = False,
) -> dict[str, Any]:
    """Build a Context Pack from provenance-aware recall results."""
    primary: list[dict[str, Any]] = []
    supporting: list[dict[str, Any]] = []
    superseded: list[dict[str, Any]] = []
    policy_flags = _collect_policy_flags(results)

    for item in results:
        score = float(item.get("score", 0.0))
        status = str(item.get("status", MEMORY_STATUS_ACTIVE))
        packed = _pack_item(item)
        if status == MEMORY_STATUS_SUPERSEDED:
            if include_superseded:
                superseded.append(packed)
            continue
        if status != MEMORY_STATUS_ACTIVE:
            continue
        if score >= CONTEXT_PRIMARY_SCORE_THRESHOLD:
            primary.append(packed)
        elif score >= CONTEXT_SUPPORTING_SCORE_THRESHOLD:
            supporting.append(packed)

    pack_items = primary + supporting + superseded
    abstain = decide_abstention(results, primary + supporting, policy_flags)
    confidence = max((float(item.get("score", 0.0)) for item in primary + supporting), default=0.0)
    return {
        "query": query,
        "context_pack": {
            "primary": primary,
            "supporting": supporting,
            "superseded": superseded,
        },
        "abstention": abstain,
        "meta": {
            "total_candidates": len(results),
            "pack_size": len(pack_items),
            "confidence": confidence,
            "policy_flags": policy_flags,
        },
    }


def _pack_item(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": item.get("id"),
        "content": item.get("content", ""),
        "score": item.get("score", 0.0),
        "namespace": item.get("namespace", ""),
        "memory_type": item.get("memory_type"),
        "status": item.get("status", MEMORY_STATUS_ACTIVE),
        "provenance": {
            "source": item.get("source", "unknown"),
            "rank": item.get("rank"),
            "created_at": item.get("created_at"),
            "access_count": item.get("access_count", 0),
            "policy_flags": _item_policy_flags(item),
        },
    }


def _collect_policy_flags(results: list[dict[str, Any]]) -> list[str]:
    flags: list[str] = []
    for item in results:
        for flag in _item_policy_flags(item):
            if flag not in flags:
                flags.append(flag)
    return flags


def _item_policy_flags(item: dict[str, Any]) -> list[str]:
    direct = item.get("policy_flags")
    if isinstance(direct, list):
        return [str(flag) for flag in direct]
    raw_metadata = item.get("metadata_json")
    if not isinstance(raw_metadata, str):
        return []
    try:
        metadata = json.loads(raw_metadata or "{}")
    except json.JSONDecodeError:
        return []
    flags = metadata.get("policy_flags", [])
    if not isinstance(flags, list):
        return []
    return [str(flag) for flag in flags]
