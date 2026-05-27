"""Audit event types for Mnémlet trust layer."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Literal


AuditResult = Literal["success", "blocked", "denied", "warning"]


@dataclass(frozen=True)
class AuditEvent:
    """A sanitized audit event."""

    action: str
    namespace: str
    caller: str
    result: AuditResult = "success"
    memory_id: str | None = None
    caller_identity: str | None = None
    details: dict[str, Any] = field(default_factory=dict)
