"""Unified conversation format for cross-platform memory extraction."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Literal


def parse_timestamp(value: object) -> datetime | None:
    """Best-effort parse of a message timestamp.

    Accepts epoch seconds (int/float), ISO-8601 strings (with optional ``Z``),
    existing ``datetime`` objects, or ``None``. Returns ``None`` when the value
    cannot be interpreted, so adapters never crash on unexpected input.
    """
    if value is None:
        return None
    if isinstance(value, datetime):
        return value
    if isinstance(value, (int, float)):
        try:
            return datetime.fromtimestamp(value)
        except (OverflowError, OSError, ValueError):
            return None
    if isinstance(value, str):
        try:
            return datetime.fromisoformat(value.replace("Z", "+00:00"))
        except ValueError:
            return None
    return None


@dataclass
class Message:
    """A single message in a conversation."""
    role: Literal["user", "assistant", "system"]
    content: str
    timestamp: datetime | None = None
    metadata: dict = field(default_factory=dict)


@dataclass
class Conversation:
    """A unified conversation session."""
    messages: list[Message]
    platform: str  # "openwebui", "claude_code", "opencode", "openclaw", "generic"
    session_id: str | None = None
    user_id: str | None = None
    namespace: str = "default"
    started_at: datetime | None = None
    ended_at: datetime | None = None
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        """Serialize to dict for storage."""
        return {
            "messages": [
                {
                    "role": m.role,
                    "content": m.content,
                    "timestamp": m.timestamp.isoformat() if m.timestamp else None,
                    "metadata": m.metadata,
                }
                for m in self.messages
            ],
            "platform": self.platform,
            "session_id": self.session_id,
            "user_id": self.user_id,
            "namespace": self.namespace,
            "started_at": self.started_at.isoformat() if self.started_at else None,
            "ended_at": self.ended_at.isoformat() if self.ended_at else None,
            "metadata": self.metadata,
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Conversation":
        """Deserialize from dict."""
        messages = [
            Message(
                role=m["role"],
                content=m["content"],
                timestamp=datetime.fromisoformat(m["timestamp"]) if m.get("timestamp") else None,
                metadata=m.get("metadata", {}),
            )
            for m in data.get("messages", [])
        ]
        return cls(
            messages=messages,
            platform=data.get("platform", "generic"),
            session_id=data.get("session_id"),
            user_id=data.get("user_id"),
            namespace=data.get("namespace", "default"),
            started_at=datetime.fromisoformat(data["started_at"]) if data.get("started_at") else None,
            ended_at=datetime.fromisoformat(data["ended_at"]) if data.get("ended_at") else None,
            metadata=data.get("metadata", {}),
        )
