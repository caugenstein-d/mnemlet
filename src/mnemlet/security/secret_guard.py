"""Regex-based secret guard for write-path content."""

from __future__ import annotations

import re
from dataclasses import dataclass
from typing import Literal


SecretGuardAction = Literal["block", "warn", "allow"]


@dataclass(frozen=True)
class SecretFinding:
    """A sanitized secret pattern match location."""

    pattern_type: str
    start: int
    end: int


@dataclass(frozen=True)
class SecretGuardResult:
    """Sanitized secret scan result."""

    clean: bool
    findings: list[SecretFinding]
    safe_summary: str
    action: str
    blocked: bool


class SecretGuard:
    """Detect and enforce conservative secret regex patterns."""

    _PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
        ("github_pat", re.compile(r"ghp_[0-9A-Za-z]{36}")),
        ("openai_key", re.compile(r"sk-[0-9A-Za-z]{48}")),
        ("aws_access_key", re.compile(r"AKIA[0-9A-Z]{16}")),
        (
            "password_assignment",
            re.compile(r"(?:password|passwd|pwd)\s*[=:]\s*\S+", re.IGNORECASE),
        ),
        (
            "generic_api_key",
            re.compile(r"(?:api.?key|token|secret)\s*[=:]\s*[0-9a-fA-F]{32,}", re.IGNORECASE),
        ),
    )

    def scan(self, content: str) -> SecretGuardResult:
        """Scan content and return sanitized pattern findings."""
        findings: list[SecretFinding] = []
        for pattern_type, pattern in self._PATTERNS:
            for match in pattern.finditer(content):
                findings.append(SecretFinding(pattern_type, match.start(), match.end()))
        return self._result(findings, action="block")

    def enforce(self, content: str, action: SecretGuardAction) -> SecretGuardResult:
        """Apply a secret guard action to content."""
        if action == "allow":
            return SecretGuardResult(clean=True, findings=[], safe_summary="clean", action=action, blocked=False)
        if action not in ("block", "warn"):
            raise ValueError("invalid secret guard action")
        scanned = self.scan(content)
        return self._result(scanned.findings, action=action)

    def _result(self, findings: list[SecretFinding], action: SecretGuardAction) -> SecretGuardResult:
        """Build a sanitized result from findings."""
        clean = not findings
        pattern_types = sorted({finding.pattern_type for finding in findings})
        safe_summary = "clean" if clean else "secret patterns detected: " + ", ".join(pattern_types)
        return SecretGuardResult(
            clean=clean,
            findings=findings,
            safe_summary=safe_summary,
            action=action,
            blocked=action == "block" and not clean,
        )
