"""Claude Desktop conversation adapter."""

from datetime import datetime
from ..conversation import Conversation, Message


class ClaudeDesktopAdapter:
    """
    Normalize Claude Desktop chat format to unified Conversation.

    Claude Desktop format (from ~/Library/Application Support/Claude/):
    {
        "conversation_id": "...",
        "project": "my-project",  # Optional: Claude Desktop projects
        "messages": [
            {
                "role": "user",
                "content": "...",
                "timestamp": 1716883200,
                "attachments": [{"type": "file", "path": "/path/to/file"}]
            },
            {
                "role": "assistant",
                "content": "...",
                "timestamp": 1716883201,
                "tool_use": [{"tool": "read_file", "input": {...}}]
            }
        ]
    }
    """

    @staticmethod
    def normalize(raw_data: dict) -> Conversation:
        """Normalize Claude Desktop format to unified Conversation."""
        messages = []
        for msg in raw_data.get("messages", []):
            metadata = {}

            # Claude Desktop-specific: track attachments
            if "attachments" in msg:
                metadata["claude_attachments"] = msg["attachments"]

            # Claude Desktop-specific: track tool use
            if "tool_use" in msg:
                metadata["claude_tool_use"] = msg["tool_use"]

            messages.append(
                Message(
                    role=msg["role"],
                    content=msg["content"],
                    timestamp=datetime.fromtimestamp(msg["timestamp"]) if msg.get("timestamp") else None,
                    metadata=metadata,
                )
            )

        # Claude Desktop projects → namespace
        project = raw_data.get("project")
        namespace = f"claude_desktop/{project}" if project else "claude_desktop/default"

        return Conversation(
            messages=messages,
            platform="claude_desktop",
            session_id=raw_data.get("conversation_id"),
            user_id=raw_data.get("user_id"),
            namespace=namespace,
            started_at=messages[0].timestamp if messages else None,
            ended_at=messages[-1].timestamp if messages else None,
            metadata={"claude_project": project},
        )
