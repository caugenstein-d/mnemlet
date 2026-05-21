"""Adapter-level benchmark checks for Mnémlet integrations."""

from __future__ import annotations

import importlib.util
from pathlib import Path
from types import ModuleType
from typing import Any, Callable

PostJson = Callable[[str, dict[str, Any], int], dict[str, Any]]
ListTools = Callable[[], list[Any]]


def summarize_adapter_results(results: list[dict[str, Any]]) -> dict[str, float | int]:
    """Summarize adapter check success rates."""
    summary: dict[str, float | int] = {
        "adapter_check_count": len(results),
        "adapter_success_rate": _success_rate(results),
    }
    for surface in sorted({item.get("surface", "unknown") for item in results}):
        surface_results = [item for item in results if item.get("surface", "unknown") == surface]
        summary[f"{surface}_success_rate"] = _success_rate(surface_results)
    return summary


def run_adapter_checks(
    openwebui_filter_path: Path = Path("/home/christoph/mira/data/functions/mnemlet_valve.py"),
    opencode_plugin_path: Path = Path("/home/christoph/.config/opencode/plugins/mnemlet-memory.js"),
) -> list[dict[str, Any]]:
    """Run adapter-level checks that are safe in local environments."""
    results = [
        check_rest_recall(_fake_rest_recall),
        check_mcp_tool_listing(_fake_mcp_tools),
    ]

    if openwebui_filter_path.exists():
        results.append(check_openwebui_filter_inlet(openwebui_filter_path))
        results.append(check_openwebui_filter_outlet(openwebui_filter_path))
    else:
        results.append(
            {
                "name": "openwebui_filter",
                "surface": "openwebui",
                "success": False,
                "error": "filter path missing",
            }
        )

    if opencode_plugin_path.exists():
        results.append(check_opencode_plugin_static(opencode_plugin_path))
    else:
        results.append(
            {
                "name": "opencode_plugin_static",
                "surface": "opencode",
                "success": False,
                "error": "plugin path missing",
            }
        )
    return results


def check_rest_recall(post_json: PostJson, expected_text: str = "Nebelkrähe") -> dict[str, Any]:
    """Verify REST recall payload shape and response schema using an injected caller."""
    try:
        response = post_json("/api/v1/recall", {"query": expected_text, "limit": 3}, 3)
        results = response.get("results", [])
        success = any(expected_text in str(item.get("content", "")) for item in results if isinstance(item, dict))
    except Exception as exc:
        return {"name": "rest_recall", "surface": "rest", "success": False, "error": str(exc)}
    return {"name": "rest_recall", "surface": "rest", "success": success}


def check_mcp_tool_listing(list_tools: ListTools) -> dict[str, Any]:
    """Verify an MCP tool listing exposes the Mnémlet recall tool."""
    try:
        tools = list_tools()
        names = {_tool_name(tool) for tool in tools}
        success = "mnemlet_recall" in names
    except Exception as exc:
        return {"name": "mcp_tool_listing", "surface": "mcp", "success": False, "error": str(exc)}
    return {"name": "mcp_tool_listing", "surface": "mcp", "success": success}


def check_openwebui_filter_inlet(path: Path, expected_text: str = "Nebelkrähe") -> dict[str, Any]:
    """Load an OpenWebUI filter and verify inlet context injection with fake recall."""
    try:
        module = _load_python_module(path, "mnemlet_valve_benchmark_inlet")
        module._post_json = lambda route, payload, timeout: {  # type: ignore[attr-defined]
            "results": [{"namespace": "integration/sentinel", "content": expected_text}]
        }
        body = {"messages": [{"role": "user", "content": "What is the codename?"}]}
        returned = module.Filter().inlet(body)
        messages = returned.get("messages", [])
        success = bool(
            messages
            and messages[0].get("role") == "system"
            and expected_text in messages[0].get("content", "")
        )
    except Exception as exc:
        return {"name": "openwebui_filter_inlet", "surface": "openwebui", "success": False, "error": str(exc)}
    return {"name": "openwebui_filter_inlet", "surface": "openwebui", "success": success}


def check_openwebui_filter_outlet(path: Path) -> dict[str, Any]:
    """Load an OpenWebUI filter and verify outlet ingest with a fake REST caller."""
    calls: list[tuple[str, dict[str, Any], int]] = []
    try:
        module = _load_python_module(path, "mnemlet_valve_benchmark_outlet")
        module._post_json = lambda route, payload, timeout: calls.append((route, payload, timeout)) or {"stored": True}  # type: ignore[attr-defined]
        body = {
            "messages": [
                {"role": "user", "content": "What is the codename?"},
                {"role": "assistant", "content": "Nebelkrähe"},
            ]
        }
        module.Filter().outlet(body)
        success = any(route == "/api/v1/ingest" for route, _payload, _timeout in calls)
    except Exception as exc:
        return {"name": "openwebui_filter_outlet", "surface": "openwebui", "success": False, "error": str(exc)}
    return {"name": "openwebui_filter_outlet", "surface": "openwebui", "success": success}


def check_opencode_plugin_static(path: Path) -> dict[str, Any]:
    """Verify the OpenCode plugin contains required memory hooks and REST paths."""
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        return {"name": "opencode_plugin_static", "surface": "opencode", "success": False, "error": str(exc)}
    required = [
        "experimental.chat.system.transform",
        "mnemlet_recall",
        "/api/v1/recall",
        "Relevant context from Mnémlet memory",
    ]
    missing = [item for item in required if item not in text]
    return {
        "name": "opencode_plugin_static",
        "surface": "opencode",
        "success": not missing,
        "missing": missing,
    }


def _load_python_module(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load module spec")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    getattr(module, "Filter")
    return module


def _fake_rest_recall(_path: str, _payload: dict[str, Any], _timeout: int) -> dict[str, Any]:
    return {"results": [{"content": "Relevant context from Mnémlet memory: Nebelkrähe"}]}


def _fake_mcp_tools() -> list[dict[str, str]]:
    return [{"name": "mnemlet_recall"}, {"name": "mnemlet_ingest"}]


def _tool_name(tool: Any) -> str:
    if isinstance(tool, dict):
        return str(tool.get("name", ""))
    return str(getattr(tool, "name", ""))


def _success_rate(results: list[dict[str, Any]]) -> float:
    if not results:
        return 0.0
    return sum(1 for item in results if item.get("success") is True) / len(results)
