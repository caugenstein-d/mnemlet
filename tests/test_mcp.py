"""Integration tests for the MCP server lifecycle."""

import json
import tempfile
from pathlib import Path
from typing import Any

import pytest

from mnemlet.config import MnemletConfig
from mnemlet.security.audit import AuditEvent
from mnemlet.server.app import create_app
from mnemlet.server.mcp_server import create_mcp_server


def _test_config(base: Path) -> MnemletConfig:
    """Build an isolated config for MCP tests."""
    return MnemletConfig(
        data_dir=base,
        sqlite_path=base / "mnemlet.db",
        chroma_path=base / "chroma",
        vault_path=base / "vault",
        embedding_cache_dir=base / "models",
    )


def _tool_result_json(result: list[Any]) -> dict[str, Any]:
    """Decode FastMCP's direct-call text result into JSON."""
    text = result[0].text
    return json.loads(text)


@pytest.mark.asyncio
async def test_mcp_session_manager_starts_during_app_lifespan() -> None:
    """FastMCP's streamable HTTP session manager is active during app lifespan."""
    with tempfile.TemporaryDirectory() as tmpdir:
        app = create_app(_test_config(Path(tmpdir)))

        assert hasattr(app.state, "mcp_session_manager")
        assert app.state.mcp_session_manager._task_group is None

        async with app.router.lifespan_context(app):
            assert app.state.mcp_session_manager._task_group is not None

        assert app.state.mcp_session_manager._task_group is None


def test_mcp_module_documents_v0_3_audit_tool() -> None:
    """MCP module documentation advertises the v0.3 tool count after audit lands."""
    from mnemlet.server import mcp_server

    assert "15 tools" in (mcp_server.__doc__ or "")


@pytest.mark.asyncio
async def test_mcp_audit_tool_registered_during_lifespan() -> None:
    """The MCP server exposes an audit tool for v0.3."""
    with tempfile.TemporaryDirectory() as tmpdir:
        app = create_app(_test_config(Path(tmpdir)))
        async with app.router.lifespan_context(app):
            tools = await app.state.mcp_session_manager._mcp_server.list_tools()
    assert any(getattr(tool, "name", "") == "mnemlet_audit" for tool in tools)


@pytest.mark.asyncio
async def test_mcp_audit_tool_returns_filtered_events_and_clamps_limit() -> None:
    """The MCP audit tool delegates filters and clamps excessive limits."""
    with tempfile.TemporaryDirectory() as tmpdir:
        app = create_app(_test_config(Path(tmpdir)))
        async with app.router.lifespan_context(app):
            app.state.db.record_audit(
                AuditEvent(action="ingest", namespace="mcp-test", caller="mcp")
            )
            app.state.db.record_audit(
                AuditEvent(action="recall", namespace="other", caller="mcp")
            )
            mcp = create_mcp_server(app.state)

            result = _tool_result_json(
                await mcp.call_tool(
                    "mnemlet_audit",
                    {"namespace": "mcp-test", "action": "ingest", "limit": 999},
                )
            )

    assert result["count"] == 1
    assert result["events"][0]["namespace"] == "mcp-test"
    assert result["events"][0]["action"] == "ingest"
