"""Tests for v0.3 audit logging."""

from __future__ import annotations

import tempfile
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from mnemlet.config import MnemletConfig
from mnemlet.security.audit import AuditEvent
from mnemlet.server.app import create_app
from mnemlet.server.mcp_server import create_mcp_server
from mnemlet.storage.sqlite import MnemletDB


def test_audit_schema_is_created(tmp_path: Path) -> None:
    db = MnemletDB(tmp_path / "mnemlet.db")
    try:
        assert "audit_log" in db._list_tables()
    finally:
        db.close()


def test_record_and_query_audit_event(tmp_path: Path) -> None:
    db = MnemletDB(tmp_path / "mnemlet.db")
    try:
        db.record_audit(AuditEvent(action="ingest", namespace="preferences", caller="rest", result="success"))
        rows = db.query_audit(namespace="preferences", action="ingest", limit=10)
    finally:
        db.close()

    assert len(rows) == 1
    assert rows[0]["action"] == "ingest"
    assert rows[0]["details"] == {}


@asynccontextmanager
async def _client(api_key: str | None = None) -> AsyncIterator[AsyncClient]:
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        config = MnemletConfig(
            data_dir=base,
            sqlite_path=base / "mnemlet.db",
            chroma_path=base / "chroma",
            vault_path=base / "vault",
            embedding_cache_dir=base / "models",
            api_key=api_key,
        )
        app = create_app(config)
        async with app.router.lifespan_context(app):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                yield client


@pytest.mark.asyncio
async def test_audit_route_returns_recent_events() -> None:
    async with _client() as client:
        await client.get("/api/v1/status")
        response = await client.get("/api/v1/audit")

    assert response.status_code == 200
    assert response.json()["count"] >= 1


@pytest.mark.asyncio
async def test_auth_denial_is_audited_without_key_material() -> None:
    key = "mnemlet_secret_key_1234567890abcdef"
    async with _client(api_key=key) as client:
        denied = await client.get("/api/v1/status", headers={"X-Mnemlet-Key": "wrong-secret"})
        allowed = await client.get("/api/v1/audit", headers={"X-Mnemlet-Key": key})

    assert denied.status_code == 401
    body = str(allowed.json())
    assert "wrong-secret" not in body
    assert any(event["result"] == "denied" for event in allowed.json()["events"])


@pytest.mark.asyncio
async def test_mcp_ingest_records_sanitized_audit_event() -> None:
    """MCP write tools record caller=mcp without storing request body content."""
    secret_content = "do not audit this content or mnemlet_secret_key_1234567890abcdef"
    async with _client() as client:
        mcp = create_mcp_server(client._transport.app.state)
        await mcp.call_tool(
            "mnemlet_ingest",
            {"content": secret_content, "namespace": "mcp-audit", "importance": 0.4},
        )
        events = client._transport.app.state.db.query_audit(
            namespace="mcp-audit",
            action="ingest",
            limit=10,
        )

    assert len(events) == 1
    assert events[0]["caller"] == "mcp"
    assert events[0]["memory_id"]
    assert secret_content not in str(events[0])
    assert "mnemlet_secret_key_1234567890abcdef" not in str(events[0])


@pytest.mark.asyncio
async def test_mcp_recall_records_sanitized_audit_event() -> None:
    """MCP read tools record caller=mcp without storing request query content."""
    secret_query = "find mnemlet_secret_key_1234567890abcdef"
    async with _client() as client:
        mcp = create_mcp_server(client._transport.app.state)
        await mcp.call_tool(
            "mnemlet_ingest",
            {"content": "visible test memory", "namespace": "mcp-recall", "importance": 0.4},
        )
        await mcp.call_tool(
            "mnemlet_recall",
            {"query": secret_query, "namespace": "mcp-recall", "limit": 5},
        )
        events = client._transport.app.state.db.query_audit(
            namespace="mcp-recall",
            action="recall",
            limit=10,
        )

    assert len(events) == 1
    assert events[0]["caller"] == "mcp"
    assert secret_query not in str(events[0])
    assert "mnemlet_secret_key_1234567890abcdef" not in str(events[0])
