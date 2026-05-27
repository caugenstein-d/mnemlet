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
