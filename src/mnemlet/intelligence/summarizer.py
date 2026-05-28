"""LLM-based conversation summarization."""

from typing import Any
from .conversation import Conversation


class ConversationSummarizer:
    """
    Summarize entire conversations into a single memory.

    Useful for:
    - Long technical discussions
    - Problem-solving sessions
    - Project planning conversations
    """

    def __init__(self, llm_client: Any):
        self.llm = llm_client

    def summarize(self, conversation: Conversation) -> dict | None:
        """
        Summarize conversation into a single memory.

        Returns a memory dict, or ``None`` when there is nothing to summarize
        (empty conversation or empty model output):
        {
            "content": "Christoph discussed Mnémlet v0.4 planning ...",
            "importance": 0.7,
            "namespace": "projects/mnemlet",
        }
        """
        if not conversation.messages:
            return None

        prompt = self._build_prompt(conversation)
        response = self.llm.generate(prompt)
        content = (response or "").strip()
        if not content:
            return None

        return {
            "content": content,
            "importance": 0.7,
            "namespace": conversation.namespace,
        }

    def _build_prompt(self, conversation: Conversation) -> str:
        """Build summarization prompt."""
        messages_text = "\n".join(
            f"{m.role.upper()}: {m.content}" for m in conversation.messages
        )

        return f"""Summarize this conversation in 2-3 sentences. Focus on:
- What was discussed
- Key decisions made
- Important outcomes or next steps

Conversation:
{messages_text}

Summary:"""
