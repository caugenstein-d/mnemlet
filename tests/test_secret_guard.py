"""Tests for v0.3 Secret Regex Guard."""

from __future__ import annotations

import tempfile
import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from mcp.server.fastmcp.exceptions import ToolError

from mnemlet.config import MnemletConfig
from mnemlet.security.secret_guard import SecretGuard, SecretGuardAction, SecretGuardResult
from mnemlet.server.app import create_app
from mnemlet.server.mcp_server import create_mcp_server


def test_secret_guard_detects_github_pat() -> None:
    result = SecretGuard().scan("token=ghp_abcdefghijklmnopqrstuvwxyzABCDEFGHIJ")
    assert result.clean is False
    assert result.findings[0].pattern_type == "github_pat"
    assert "ghp_" not in result.safe_summary


def test_secret_guard_detects_openai_key() -> None:
    key = "sk-" + "a" * 48
    result = SecretGuard().scan(f"OPENAI_API_KEY={key}")
    assert result.clean is False
    assert result.findings[0].pattern_type == "openai_key"


def test_secret_guard_detects_password_assignment() -> None:
    result = SecretGuard().scan("password = hunter2")
    assert result.clean is False
    assert result.findings[0].pattern_type == "password_assignment"


def test_secret_guard_warn_action_reports_findings_without_blocking() -> None:
    result = SecretGuard().enforce("password = hunter2", action="warn")

    assert result.clean is False
    assert result.action == "warn"
    assert result.blocked is False


@asynccontextmanager
async def _client() -> AsyncIterator[AsyncClient]:
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        config = MnemletConfig(
            data_dir=base,
            sqlite_path=base / "mnemlet.db",
            chroma_path=base / "chroma",
            vault_path=base / "vault",
            embedding_cache_dir=base / "models",
        )
        app = create_app(config)
        async with app.router.lifespan_context(app):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                yield client


@pytest.mark.asyncio
async def test_ingest_blocks_secret_by_default() -> None:
    key = "sk-" + "a" * 48
    async with _client() as client:
        response = await client.post("/api/v1/ingest", json={"content": f"token {key}", "namespace": "default"})
        audit = await client.get("/api/v1/audit", params={"action": "ingest"})

    assert response.status_code == 400
    assert "openai_key" in str(response.json())
    assert key not in str(response.json())
    assert any(event["result"] == "blocked" for event in audit.json()["events"])


@pytest.mark.asyncio
async def test_mcp_update_blocks_secret_content_without_storing_key_material() -> None:
    key = "sk-" + "a" * 48
    async with _client() as client:
        app_state = client._transport.app.state
        mcp = create_mcp_server(app_state)
        result = await mcp.call_tool(
            "mnemlet_ingest",
            {"content": "safe initial memory", "namespace": "mcp-update", "importance": 0.4},
        )
        memory_id = json.loads(result[0].text)["memory_id"]

        with pytest.raises(ToolError) as exc_info:
            await mcp.call_tool(
                "mnemlet_update",
                {"memory_id": memory_id, "content": f"replacement {key}"},
            )

        memory = app_state.db.get_memory(memory_id)
        events = app_state.db.query_audit(namespace="mcp-update", action="update", limit=10)

    assert "openai_key" in str(exc_info.value)
    assert key not in str(exc_info.value)
    assert memory is not None
    assert key not in memory["content_preview"]
    assert memory["content_preview"] == "safe initial memory"
    assert any(event["result"] == "blocked" for event in events)
    assert "openai_key" in str(events)
    assert key not in str(events)
