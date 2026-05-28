"""Cursor IDE conversation adapter."""

from datetime import datetime
from ..conversation import Conversation, Message


class CursorAdapter:
    """
    Normalize Cursor IDE chat format to unified Conversation.

    Cursor format (from ~/.cursor/mcp.json or .cursor/mcp.json):
    {
        "conversation_id": "...",
        "messages": [
            {
                "role": "user",
                "content": "...",
                "timestamp": "2026-05-28T10:00:00Z",
                "context": {"files": ["src/main.py"], "selection": "..."}
            },
            {
                "role": "assistant",
                "content": "...",
                "timestamp": "2026-05-28T10:00:01Z",
                "code_changes": [{"file": "src/main.py", "diff": "..."}]
            }
        ]
    }
    """

    @staticmethod
    def normalize(raw_data: dict) -> Conversation:
        """Normalize Cursor format to unified Conversation."""
        messages = []
        for msg in raw_data.get("messages", []):
            metadata = {}

            # Cursor-specific: track file context
            if "context" in msg:
                metadata["cursor_context"] = msg["context"]

            # Cursor-specific: track code changes
            if "code_changes" in msg:
                metadata["cursor_code_changes"] = msg["code_changes"]

            timestamp = None
            if msg.get("timestamp"):
                try:
                    timestamp = datetime.fromisoformat(msg["timestamp"].replace("Z", "+00:00"))
                except (ValueError, AttributeError):
                    pass

            messages.append(
                Message(
                    role=msg["role"],
                    content=msg["content"],
                    timestamp=timestamp,
                    metadata=metadata,
                )
            )

        return Conversation(
            messages=messages,
            platform="cursor",
            session_id=raw_data.get("conversation_id"),
            user_id=raw_data.get("user_id"),
            namespace=raw_data.get("namespace", "cursor/default"),
            started_at=messages[0].timestamp if messages else None,
            ended_at=messages[-1].timestamp if messages else None,
            metadata={"cursor_version": raw_data.get("cursor_version")},
        )
