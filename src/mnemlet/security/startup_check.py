"""Startup security checks for local Mnémlet deployments."""

from __future__ import annotations

import stat
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from mnemlet.security.auth import key_configured


@dataclass(frozen=True)
class SecurityCheck:
    """One startup security check result."""

    code: str
    level: str
    message: str

    def to_dict(self) -> dict[str, str]:
        """Serialize for status responses."""
        return asdict(self)


def _is_group_or_world_readable(path: Path) -> bool:
    """Return whether group or others can read a path."""
    if not path.exists():
        return False
    mode = path.stat().st_mode
    return bool(mode & (stat.S_IRGRP | stat.S_IROTH))


def run_startup_security_checks(config: Any) -> list[SecurityCheck]:
    """Return non-blocking startup security warnings for a config."""
    checks: list[SecurityCheck] = []
    if getattr(config, "server_host", "127.0.0.1") == "0.0.0.0":
        checks.append(SecurityCheck("public_host", "warning", "server is bound to 0.0.0.0"))
    if not key_configured(getattr(config, "api_key", None)):
        checks.append(SecurityCheck("auth_missing", "warning", "no API key configured"))
    for path_attr in ("sqlite_path", "vault_path", "data_dir"):
        path = Path(getattr(config, path_attr))
        if _is_group_or_world_readable(path):
            checks.append(SecurityCheck("unsafe_permissions", "warning", f"{path.name} is group/world readable"))
    if "*" in getattr(config, "cors_origins", ["http://localhost", "http://127.0.0.1"]):
        checks.append(SecurityCheck("cors_wildcard", "warning", "CORS allows all origins"))
    return checks
