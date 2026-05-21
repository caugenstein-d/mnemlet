"""Integration tests for the MCP server lifecycle."""

import tempfile
from pathlib import Path

import pytest

from mnemlet.config import MnemletConfig
from mnemlet.server.app import create_app


def _test_config(base: Path) -> MnemletConfig:
    """Build an isolated config for MCP tests."""
    return MnemletConfig(
        data_dir=base,
        sqlite_path=base / "mnemlet.db",
        chroma_path=base / "chroma",
        vault_path=base / "vault",
        embedding_cache_dir=base / "models",
    )


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
