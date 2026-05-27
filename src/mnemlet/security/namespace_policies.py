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

BOOLEAN_POLICIES: set[str] = {"allow_recall", "allow_ingest", "confirm_before_forget"}
SECRET_GUARD_ACTIONS: set[str] = {"block", "warn", "allow"}


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


def validate_namespace_policy_value(policy_key: str, policy_value: str) -> str:
    """Validate and return a namespace policy value safe to persist."""
    value = policy_value.strip()
    if policy_key not in DEFAULT_POLICIES:
        raise ValueError(f"unknown namespace policy: {policy_key}")
    if policy_key in BOOLEAN_POLICIES:
        policy_value_bool(value)
        return value
    if policy_key == "secret_guard_action":
        if value not in SECRET_GUARD_ACTIONS:
            raise ValueError(f"invalid secret_guard_action policy value: {policy_value}")
        return value
    if policy_key == "max_memories":
        try:
            parsed = int(value)
        except ValueError as exc:
            raise ValueError(f"invalid max_memories policy value: {policy_value}") from exc
        if parsed < 0:
            raise ValueError(f"invalid max_memories policy value: {policy_value}")
        return value
    return value
