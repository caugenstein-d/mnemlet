"""Fixed MVP lifecycle policies for Memory Intelligence Core v0.2."""

from __future__ import annotations

from mnemlet.constants import (
    MEMORY_STATUS_ACTIVE,
    MEMORY_STATUS_SUPERSEDED,
    MEMORY_TYPE_CONTEXT,
    MEMORY_TYPE_FACT,
    MEMORY_TYPE_PREFERENCE,
)

AUTO_SUPERSEDE_TYPES = {
    MEMORY_TYPE_FACT,
    MEMORY_TYPE_PREFERENCE,
    MEMORY_TYPE_CONTEXT,
}


def can_auto_supersede(memory_type: str | None) -> bool:
    """Return whether a memory type may be automatically superseded."""
    return memory_type in AUTO_SUPERSEDE_TYPES


def recall_statuses(include_superseded: bool = False) -> set[str]:
    """Return statuses eligible for recall/context assembly."""
    if include_superseded:
        return {MEMORY_STATUS_ACTIVE, MEMORY_STATUS_SUPERSEDED}
    return {MEMORY_STATUS_ACTIVE}
