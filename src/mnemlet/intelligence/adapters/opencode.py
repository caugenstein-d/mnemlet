"""OpenCode conversation adapter."""

from ..conversation import Conversation
from ._common import build_messages, session_id_of


class OpenCodeAdapter:
    """
    Normalize OpenCode session format to unified Conversation.

    {
        "session_id": "...",
        "messages": [
            {"role": "user", "content": "...", "timestamp": ...},
            {"role": "assistant", "content": "...", "timestamp": ...}
        ]
    }
    """

    @staticmethod
    def normalize(raw_data: dict) -> Conversation:
        messages = build_messages(raw_data.get("messages"))
        return Conversation(
            messages=messages,
            platform="opencode",
            session_id=session_id_of(raw_data),
            user_id=raw_data.get("user_id"),
            namespace=raw_data.get("namespace", "opencode/default"),
            started_at=messages[0].timestamp if messages else None,
            ended_at=messages[-1].timestamp if messages else None,
        )
