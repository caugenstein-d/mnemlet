"""Claude Code (CLI) conversation adapter."""

from ..conversation import Conversation
from ._common import build_messages, session_id_of


class ClaudeCodeAdapter:
    """
    Normalize Claude Code session format to unified Conversation.

    Claude Code sends agent sessions, optionally scoped to a project/cwd:
    {
        "session_id": "...",
        "project": "mnemlet",          # optional → namespace
        "messages": [
            {"role": "user", "content": "...", "timestamp": "2026-05-28T10:00:00Z"},
            {"role": "assistant", "content": "...", "timestamp": 1716883201}
        ]
    }
    Timestamps may be epoch seconds or ISO-8601.
    """

    @staticmethod
    def normalize(raw_data: dict) -> Conversation:
        messages = build_messages(raw_data.get("messages"))
        project = raw_data.get("project")
        namespace = raw_data.get("namespace") or (
            f"claude_code/{project}" if project else "claude_code/default"
        )
        return Conversation(
            messages=messages,
            platform="claude_code",
            session_id=session_id_of(raw_data),
            user_id=raw_data.get("user_id"),
            namespace=namespace,
            started_at=messages[0].timestamp if messages else None,
            ended_at=messages[-1].timestamp if messages else None,
            metadata={"project": project} if project else {},
        )
