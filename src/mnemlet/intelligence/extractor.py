"""LLM-based memory extraction from conversations."""

import json
from typing import Any
from .conversation import Conversation


# Categories the extractor is asked to produce. Kept as free-form labels stored
# alongside each extracted memory (not the same as ingest's memory_type enum).
EXTRACTION_TYPES = ("preference", "fact", "decision", "context")


class MemoryExtractor:
    """
    Extract individual memories from a conversation using LLM.

    Extracts:
    - User preferences (e.g., "Christoph prefers dark mode")
    - Facts about user (e.g., "Christoph works on Mnémlet")
    - Decisions made (e.g., "Christoph decided to use SQLite")
    - Important context (e.g., "Christoph's Pi has 16GB RAM")
    """

    def __init__(self, llm_client: Any):
        """
        llm_client: Ollama client or compatible API exposing ``generate(prompt)``.
        """
        self.llm = llm_client

    def extract(self, conversation: Conversation) -> list[dict]:
        """
        Extract memories from conversation.

        Returns list of:
        {
            "content": "Christoph prefers dark mode",
            "type": "preference",  # preference, fact, decision, context
            "importance": 0.8,
            "namespace": "preferences",
        }
        """
        if not conversation.messages:
            return []
        prompt = self._build_prompt(conversation)
        response = self.llm.generate(prompt)
        return self._parse_response(response, conversation)

    def _build_prompt(self, conversation: Conversation) -> str:
        """Build extraction prompt."""
        messages_text = "\n".join(
            f"{m.role.upper()}: {m.content}" for m in conversation.messages
        )

        return f"""Analyze this conversation and extract important memories about the user.

Conversation:
{messages_text}

Extract memories in these categories:
- preference: User preferences (e.g., "prefers dark mode", "likes Python")
- fact: Facts about the user (e.g., "works on project X", "uses Raspberry Pi")
- decision: Decisions made (e.g., "decided to use SQLite", "chose MIT license")
- context: Important context (e.g., "has 16GB RAM", "runs on Pi 5")

For each memory, provide:
- content: Clear, concise statement (e.g., "Christoph prefers dark mode in all editors")
- type: One of [preference, fact, decision, context]
- importance: 0.0-1.0 (how important is this for future conversations?)
- namespace: Suggested namespace (e.g., "preferences", "projects/mnemlet", "infrastructure")

Return as JSON array:
[
  {{"content": "...", "type": "...", "importance": 0.8, "namespace": "..."}},
  ...
]

If no important memories found, return empty array: []

Extracted memories:"""

    def _parse_response(self, response: str, conversation: Conversation | None = None) -> list[dict]:
        """Parse LLM response into memory list."""
        default_namespace = conversation.namespace if conversation else "default"
        try:
            # Try to extract a JSON array from the response
            start = response.find("[")
            end = response.rfind("]") + 1
            if start >= 0 and end > start:
                json_str = response[start:end]
                memories = json.loads(json_str)

                # Validate and normalize
                validated = []
                for mem in memories:
                    if not isinstance(mem, dict):
                        continue
                    content = str(mem.get("content", "")).strip()
                    if not content:
                        continue
                    mem_type = mem.get("type", "context")
                    if mem_type not in EXTRACTION_TYPES:
                        mem_type = "context"
                    try:
                        importance = float(mem.get("importance", 0.5))
                    except (TypeError, ValueError):
                        importance = 0.5
                    importance = max(0.0, min(1.0, importance))
                    validated.append({
                        "content": content,
                        "type": mem_type,
                        "importance": importance,
                        "namespace": mem.get("namespace") or default_namespace,
                    })
                return validated
        except (json.JSONDecodeError, ValueError, TypeError):
            pass

        return []
