"""Shared helpers for platform adapters."""

from __future__ import annotations

from ..conversation import Message, parse_timestamp


def build_messages(raw_messages: list[dict] | None) -> list[Message]:
    """Normalize a list of raw message dicts into unified ``Message`` objects.

    Tolerant of missing fields and varied timestamp encodings so a malformed
    message never breaks an entire conversation.
    """
    messages: list[Message] = []
    for msg in raw_messages or []:
        if not isinstance(msg, dict):
            continue
        messages.append(
            Message(
                role=msg.get("role", "user"),
                content=msg.get("content", "") or "",
                timestamp=parse_timestamp(msg.get("timestamp")),
                metadata=dict(msg.get("metadata") or {}),
            )
        )
    return messages


def session_id_of(raw_data: dict) -> str | None:
    """Pick the first present session identifier from common key names."""
    for key in ("session_id", "conversation_id", "chat_id", "id"):
        value = raw_data.get(key)
        if value:
            return str(value)
    return None
