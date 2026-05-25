"""Tests for version truth across package, API, and MCP surfaces."""

from __future__ import annotations

import tempfile
import tomllib
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

import mnemlet
from mnemlet.config import MnemletConfig
from mnemlet.server.app import create_app
from mnemlet.server import mcp_server


def _project_version() -> str:
    """Read the version from pyproject.toml."""
    pyproject = Path(__file__).resolve().parents[1] / "pyproject.toml"
    with pyproject.open("rb") as f:
        return tomllib.load(f)["project"]["version"]


def _test_config(base: Path) -> MnemletConfig:
    """Build an isolated config for version endpoint tests."""
    return MnemletConfig(
        data_dir=base,
        sqlite_path=base / "mnemlet.db",
        chroma_path=base / "chroma",
        vault_path=base / "vault",
        embedding_cache_dir=base / "models",
    )


@asynccontextmanager
async def _client() -> AsyncIterator[AsyncClient]:
    """Create an isolated API client with lifespan-managed app state."""
    with tempfile.TemporaryDirectory() as tmpdir:
        app = create_app(_test_config(Path(tmpdir)))
        async with app.router.lifespan_context(app):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                yield ac


def test_package_version_matches_pyproject() -> None:
    """The importable package version follows pyproject.toml."""
    assert mnemlet.__version__ == _project_version()


def test_fastapi_app_uses_package_version() -> None:
    """FastAPI metadata exposes the package version."""
    with tempfile.TemporaryDirectory() as tmpdir:
        app = create_app(_test_config(Path(tmpdir)))

        assert app.version == mnemlet.__version__


@pytest.mark.asyncio
async def test_status_endpoint_reports_package_version() -> None:
    """GET /api/v1/status reports the package version."""
    async with _client() as client:
        resp = await client.get("/api/v1/status")

    assert resp.status_code == 200
    assert resp.json()["version"] == mnemlet.__version__


def test_mcp_module_docstring_names_current_tool_count() -> None:
    """MCP module documentation does not advertise the old 8-tool surface."""
    assert "14 tools" in (mcp_server.__doc__ or "")
    assert "8 tools" not in (mcp_server.__doc__ or "")
