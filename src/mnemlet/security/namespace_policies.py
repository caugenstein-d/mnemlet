"""Namespace policy helpers for Mnémlet v0.3."""

from __future__ import annotations

from dataclasses import dataclass


DEFAULT_POLICIES: dict[str, str] = {
    "secret_guard_action": "block",
    "allow_recall": "true",
    "allow_ingest": "true",
    "confirm_before_forget": "false",
    "max_memories": "0",
}


@dataclass(frozen=True)
class NamespacePolicy:
    """One namespace policy value."""

    namespace: str
    policy_key: str
    policy_value: str


def policy_value_bool(value: str) -> bool:
    """Parse boolean policy values."""
    normalized = value.strip().lower()
    if normalized in {"true", "1", "yes", "on"}:
        return True
    if normalized in {"false", "0", "no", "off"}:
        return False
    raise ValueError(f"invalid boolean policy value: {value}")
