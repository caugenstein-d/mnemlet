"""Tests for adapter-level benchmark checks."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from mnemlet.benchmark.adapters import (
    check_mcp_tool_listing,
    check_opencode_plugin_static,
    check_openwebui_filter_inlet,
    check_openwebui_filter_outlet,
    check_rest_recall,
    run_adapter_checks,
    summarize_adapter_results,
)


def test_summarize_adapter_results_counts_success_rates() -> None:
    results = [
        {"name": "rest_recall", "surface": "rest", "success": True},
        {"name": "rest_ingest", "surface": "rest", "success": True},
        {"name": "openwebui_inlet", "surface": "openwebui", "success": False, "error": "missing context"},
    ]

    summary = summarize_adapter_results(results)

    assert summary["adapter_check_count"] == 3
    assert summary["adapter_success_rate"] == 2 / 3
    assert summary["rest_success_rate"] == 1.0
    assert summary["openwebui_success_rate"] == 0.0


def test_check_rest_recall_verifies_payload_and_expected_memory() -> None:
    calls: list[tuple[str, dict[str, Any], int]] = []

    def post_json(path: str, payload: dict[str, Any], timeout: int) -> dict[str, Any]:
        calls.append((path, payload, timeout))
        return {"results": [{"content": "Relevant context from Mnémlet memory: Nebelkrähe"}]}

    result = check_rest_recall(post_json, expected_text="Nebelkrähe")

    assert result["success"] is True
    assert calls == [("/api/v1/recall", {"query": "Nebelkrähe", "limit": 3}, 3)]


def test_check_mcp_tool_listing_requires_recall_tool() -> None:
    result = check_mcp_tool_listing(lambda: [{"name": "mnemlet_recall"}, {"name": "mnemlet_ingest"}])

    assert result["success"] is True


def write_fake_filter(path: Path) -> None:
    path.write_text(
        '''
class Filter:
    def inlet(self, body, __user__=None):
        response = _post_json("/api/v1/recall", {"query": "codename"}, 3)
        memory = response["results"][0]["content"]
        body["messages"].insert(0, {"role": "system", "content": memory})
        return body

    def outlet(self, body, __user__=None):
        _post_json("/api/v1/ingest", {"content": "summary"}, 3)
        return body

def _post_json(path, payload, timeout):
    raise RuntimeError("test should monkeypatch this")
''',
        encoding="utf-8",
    )


def test_check_openwebui_filter_inlet_injects_expected_context(tmp_path: Path) -> None:
    filter_path = tmp_path / "mnemlet_valve.py"
    write_fake_filter(filter_path)

    result = check_openwebui_filter_inlet(filter_path, expected_text="Nebelkrähe")

    assert result["success"] is True


def test_check_openwebui_filter_outlet_calls_ingest(tmp_path: Path) -> None:
    filter_path = tmp_path / "mnemlet_valve.py"
    write_fake_filter(filter_path)

    result = check_openwebui_filter_outlet(filter_path)

    assert result["success"] is True


def test_check_opencode_plugin_static_requires_memory_hooks(tmp_path: Path) -> None:
    plugin_path = tmp_path / "mnemlet-memory.js"
    plugin_path.write_text(
        "experimental.chat.system.transform mnemlet_recall /api/v1/recall Relevant context from Mnémlet memory",
        encoding="utf-8",
    )

    result = check_opencode_plugin_static(plugin_path)

    assert result["success"] is True


def test_run_adapter_checks_includes_safe_rest_and_mcp_fakes() -> None:
    results = run_adapter_checks(openwebui_filter_path=Path("missing.py"), opencode_plugin_path=Path("missing.js"))

    result_names = {item["name"] for item in results}
    assert "rest_recall" in result_names
    assert "mcp_tool_listing" in result_names


def test_openwebui_filter_inlet_does_not_inject_on_empty_results(tmp_path: Path) -> None:
    filter_path = tmp_path / "mnemlet_valve.py"
    write_fake_filter(filter_path)

    result = check_openwebui_filter_inlet(filter_path, expected_text="Nebelkrähe", fake_response={"results": []})

    assert result["success"] is False
    assert result["name"] == "openwebui_filter_inlet"


def test_opencode_static_accepts_context_pack_ready_plugin(tmp_path: Path) -> None:
    plugin_path = tmp_path / "mnemlet-memory.js"
    plugin_path.write_text(
        "experimental.chat.system.transform mnemlet_recall mnemlet_context /api/v1/recall Relevant context from Mnémlet memory",
        encoding="utf-8",
    )

    result = check_opencode_plugin_static(plugin_path)

    assert result["success"] is True
