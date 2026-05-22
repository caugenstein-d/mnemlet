"""Deterministic memory type classifier for the v0.2 MVP."""

from __future__ import annotations

import re
from dataclasses import dataclass

from mnemlet.constants import (
    MEMORY_TYPE_CONTEXT,
    MEMORY_TYPE_EVENT,
    MEMORY_TYPE_FACT,
    MEMORY_TYPE_INSTRUCTION,
    MEMORY_TYPE_PREFERENCE,
)


@dataclass(frozen=True)
class ClassificationResult:
    """Result of classifying a memory."""

    memory_type: str
    confidence: float
    source: str
    summary: str


def classify_memory(content: str, namespace: str = "default") -> ClassificationResult:
    """Classify memory content into one fixed MVP memory type."""
    normalized = content.casefold()
    summary = _summary(content)
    if _contains_any(normalized, ("immer", "niemals", "muss", "darf nicht", "never", "always")):
        return ClassificationResult(MEMORY_TYPE_INSTRUCTION, 0.8, "heuristic", summary)
    if _contains_any(normalized, ("bevorzugt", "bevorzuge", "prefers", "prefer ", "mag lieber")):
        return ClassificationResult(MEMORY_TYPE_PREFERENCE, 0.75, "heuristic", summary)
    if _looks_like_event(content):
        return ClassificationResult(MEMORY_TYPE_EVENT, 0.7, "heuristic", summary)
    if _looks_like_fact(normalized):
        return ClassificationResult(MEMORY_TYPE_FACT, 0.6, "heuristic", summary)
    return ClassificationResult(MEMORY_TYPE_CONTEXT, 0.5, "heuristic", summary)


def _contains_any(text: str, needles: tuple[str, ...]) -> bool:
    return any(needle in text for needle in needles)


def _looks_like_event(content: str) -> bool:
    return bool(
        re.search(r"\b\d{4}-\d{2}-\d{2}\b", content)
        or re.search(r"\b\d{1,2}\.\s*[A-ZÄÖÜa-zäöü]+\b", content)
        or re.search(r"\b(am|um|deployment|termin|meeting)\b", content.casefold())
    )


def _looks_like_fact(text: str) -> bool:
    return _contains_any(text, (" ist ", " läuft ", " nutzt ", " uses ", " runs ", " is "))


def _summary(content: str, max_chars: int = 160) -> str:
    compact = " ".join(content.split())
    if len(compact) <= max_chars:
        return compact
    return compact[: max_chars - 1].rstrip() + "…"
