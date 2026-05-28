"""OpenWebUI conversation adapter."""

from datetime import datetime
from ..conversation import Conversation, Message


class OpenWebUIAdapter:
    """Normalize OpenWebUI chat format to unified Conversation."""

    @staticmethod
    def normalize(raw_data: dict) -> Conversation:
        """
        OpenWebUI sends messages like:
        {
            "chat_id": "...",
            "messages": [
                {"role": "user", "content": "...", "timestamp": 1234567890},
                {"role": "assistant", "content": "...", "timestamp": 1234567891}
            ]
        }
        """
        messages = []
        for msg in raw_data.get("messages", []):
            messages.append(
                Message(
                    role=msg["role"],
                    content=msg["content"],
                    timestamp=datetime.fromtimestamp(msg["timestamp"]) if msg.get("timestamp") else None,
                    metadata=msg.get("metadata", {}),
                )
            )

        return Conversation(
            messages=messages,
            platform="openwebui",
            session_id=raw_data.get("chat_id"),
            user_id=raw_data.get("user_id"),
            namespace=raw_data.get("namespace", "openwebui/default"),
            started_at=messages[0].timestamp if messages else None,
            ended_at=messages[-1].timestamp if messages else None,
        )
