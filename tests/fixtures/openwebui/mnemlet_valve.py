"""
Mnémlet Memory Filter for OpenWebUI.
title: Mnémlet Memory
author: Christoph + Mira
version: 1.1.0
"""

import json
from typing import Any
import urllib.error
import urllib.request

MNEMLET_URL = "http://localhost:4050"
RECALL_LIMIT = 3
RECALL_TIMEOUT_SECONDS = 3
INGEST_TIMEOUT_SECONDS = 3
MAX_MEMORY_CONTENT_CHARS = 800
MAX_STORED_MESSAGE_CHARS = 200


def _post_json(path: str, payload: dict[str, Any], timeout: int) -> dict[str, Any]:
    """POST JSON to Mnémlet and return a JSON object."""
    data = json.dumps(payload).encode("utf-8")
    req = urllib.request.Request(
        f"{MNEMLET_URL}{path}",
        data=data,
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        raw = resp.read().decode("utf-8")
    parsed = json.loads(raw) if raw else {}
    return parsed if isinstance(parsed, dict) else {}


def _latest_user_content(messages: list[dict[str, Any]]) -> str:
    """Return the latest user message content from an OpenWebUI message list."""
    for message in reversed(messages):
        if message.get("role") == "user":
            content = message.get("content", "")
            return content if isinstance(content, str) else ""
    return ""


def _latest_assistant_content(messages: list[dict[str, Any]]) -> str:
    """Return the latest assistant message content from an OpenWebUI message list."""
    for message in reversed(messages):
        if message.get("role") == "assistant":
            content = message.get("content", "")
            return content if isinstance(content, str) else ""
    return ""


def _format_memories(memories: list[dict[str, Any]]) -> str:
    """Format Mnémlet recall results as a bounded system context block."""
    lines = []
    for memory in memories:
        if not isinstance(memory, dict):
            continue
        namespace = memory.get("namespace") or "default"
        content = memory.get("content") or memory.get("content_preview") or ""
        if not isinstance(content, str) or not content.strip():
            continue
        clipped = content.strip()[:MAX_MEMORY_CONTENT_CHARS]
        lines.append(f"[{namespace}] {clipped}")
        if len(lines) >= RECALL_LIMIT:
            break

    if not lines:
        return ""

    return (
        "--- Relevant context from Mnémlet memory ---\n"
        + "\n".join(lines)
        + "\n---\n"
    )


class Filter:
    """OpenWebUI filter that bridges chat requests to Mnémlet memory."""

    def __init__(self) -> None:
        self.priority = 0

    def inlet(self, body: dict, __user__: dict | None = None) -> dict:
        """Before the LLM responds, inject relevant Mnémlet memories."""
        try:
            messages = body.get("messages", [])
            if not isinstance(messages, list) or not messages:
                return body

            query = _latest_user_content(messages).strip()
            if len(query) < 3:
                return body

            response = _post_json(
                "/api/v1/recall",
                {"query": query, "limit": RECALL_LIMIT, "min_score": 0.1},
                RECALL_TIMEOUT_SECONDS,
            )
            memories = response.get("results", [])
            if not isinstance(memories, list):
                return body

            context = _format_memories(memories)
            if not context:
                return body

            first_message = messages[0]
            if isinstance(first_message, dict) and first_message.get("role") == "system":
                existing = first_message.get("content", "")
                first_message["content"] = context + "\n" + (existing if isinstance(existing, str) else "")
            else:
                messages.insert(0, {"role": "system", "content": context})
            body["messages"] = messages
        except Exception as e:
            print(f"[Mnémlet inlet] {type(e).__name__}: {e}")

        return body

    def outlet(self, body: dict, __user__: dict | None = None) -> dict:
        """After the LLM responds, store a compact interaction summary."""
        try:
            messages = body.get("messages", [])
            if not isinstance(messages, list):
                return body

            last_user = _latest_user_content(messages)
            last_assistant = _latest_assistant_content(messages)
            if not last_user or not last_assistant:
                return body

            content = (
                f"User: {last_user[:MAX_STORED_MESSAGE_CHARS]}. "
                f"Assistant: {last_assistant[:MAX_STORED_MESSAGE_CHARS]}"
            )
            _post_json(
                "/api/v1/ingest",
                {
                    "content": content,
                    "namespace": "openwebui/christoph/daily_chat",
                    "importance": 0.3,
                },
                INGEST_TIMEOUT_SECONDS,
            )
        except Exception as e:
            print(f"[Mnémlet outlet] {type(e).__name__}: {e}")

        return body
