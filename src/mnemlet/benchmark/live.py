"""Environment-dependent live benchmark checks."""

from __future__ import annotations

import subprocess
import urllib.request
from typing import Any


OPENCODE_SENTINEL_PROMPT = "What is the Mnémlet OpenCode bridge called? Answer with only the codename."
OPENWEBUI_VERSION_URL = "http://127.0.0.1:8080/_app/version.json"
MAX_OUTPUT_CHARS = 2000


def run_live_checks(include_opencode: bool = False, include_openwebui: bool = False) -> list[dict[str, Any]]:
    """Run opt-in live checks against locally configured integrations."""
    results: list[dict[str, Any]] = []
    if include_opencode:
        results.append(_opencode_mcp_list())
        results.append(_opencode_run_sentinel())
    if include_openwebui:
        results.append(_openwebui_version())
    return results


def _opencode_mcp_list() -> dict[str, Any]:
    try:
        completed = subprocess.run(
            ["opencode", "mcp", "list"],
            capture_output=True,
            text=True,
            timeout=30,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired, TimeoutError) as exc:
        return {"name": "opencode_mcp_list", "surface": "opencode-live", "success": False, "error": str(exc)}

    output = f"{completed.stdout}\n{completed.stderr}"
    success = completed.returncode == 0 and "mnemlet" in output and "connected" in output
    return _subprocess_result("opencode_mcp_list", completed, success)


def _opencode_run_sentinel() -> dict[str, Any]:
    try:
        completed = subprocess.run(
            ["opencode", "run", OPENCODE_SENTINEL_PROMPT],
            capture_output=True,
            text=True,
            timeout=120,
            check=False,
        )
    except (OSError, subprocess.TimeoutExpired, TimeoutError) as exc:
        return {"name": "opencode_sentinel", "surface": "opencode-live", "success": False, "error": str(exc)}

    output = f"{completed.stdout}\n{completed.stderr}"
    success = completed.returncode == 0 and "Nebelkrähe" in output
    return _subprocess_result("opencode_sentinel", completed, success)


def _openwebui_version() -> dict[str, Any]:
    try:
        with urllib.request.urlopen(OPENWEBUI_VERSION_URL, timeout=5) as response:
            body = response.read().decode("utf-8")[:MAX_OUTPUT_CHARS]
            success = getattr(response, "status", 200) == 200
    except Exception as exc:
        return {"name": "openwebui_version", "surface": "openwebui-live", "success": False, "error": str(exc)}
    return {"name": "openwebui_version", "surface": "openwebui-live", "success": success, "body": body}


def _subprocess_result(name: str, completed: subprocess.CompletedProcess[str], success: bool) -> dict[str, Any]:
    result: dict[str, Any] = {
        "name": name,
        "surface": "opencode-live",
        "success": success,
    }
    if not success:
        result.update(
            {
                "error": f"exit {completed.returncode}",
                "returncode": completed.returncode,
                "stdout": completed.stdout[-MAX_OUTPUT_CHARS:],
                "stderr": completed.stderr[-MAX_OUTPUT_CHARS:],
            }
        )
    return result
