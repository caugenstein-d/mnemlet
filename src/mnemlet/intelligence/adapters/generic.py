"""Generic MCP-client conversation adapter (permissive fallback)."""

from ..conversation import Conversation
from ._common import build_messages, session_id_of


class GenericAdapter:
    """
    Normalize an arbitrary MCP client's chat format to unified Conversation.

    The most permissive adapter: it expects a ``messages`` list of
    ``{role, content, timestamp?}`` and accepts any of the common session-id
    keys. Used as the fallback when no platform-specific adapter matches.
    """

    @staticmethod
    def normalize(raw_data: dict) -> Conversation:
        messages = build_messages(raw_data.get("messages"))
        return Conversation(
            messages=messages,
            platform=raw_data.get("platform", "generic"),
            session_id=session_id_of(raw_data),
            user_id=raw_data.get("user_id"),
            namespace=raw_data.get("namespace", "default"),
            started_at=messages[0].timestamp if messages else None,
            ended_at=messages[-1].timestamp if messages else None,
        )
