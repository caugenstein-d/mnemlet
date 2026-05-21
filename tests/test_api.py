"""Integration tests for the REST API."""

import tempfile
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from mnemlet.server.app import create_app
from mnemlet.config import MnemletConfig


@asynccontextmanager
async def _client() -> AsyncIterator[AsyncClient]:
    """Create an isolated API client with app lifespan in the test task."""
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        config = MnemletConfig(
            data_dir=base,
            sqlite_path=base / "mnemlet.db",
            chroma_path=base / "chroma",
            embedding_cache_dir=base / "models",
        )
        app = create_app(config)
        async with app.router.lifespan_context(app):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                yield ac


@pytest.mark.asyncio
async def test_health_endpoint():
    """GET /api/v1/health returns 200."""
    async with _client() as client:
        resp = await client.get("/api/v1/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_ingest_and_recall():
    """Full ingest → recall roundtrip."""
    async with _client() as client:
        resp = await client.post("/api/v1/ingest", json={
            "content": "User prefers dark mode in all editors",
            "namespace": "preferences",
            "importance": 0.9,
        })
        assert resp.status_code == 200
        data = resp.json()
        assert data["stored"] is True

        resp = await client.post("/api/v1/recall", json={
            "query": "editor dark mode",
            "namespace": "preferences",
            "limit": 5,
        })
    assert resp.status_code == 200
    results = resp.json()["results"]
    assert len(results) >= 1


@pytest.mark.asyncio
async def test_status_endpoint():
    """GET /api/v1/status returns memory counts."""
    async with _client() as client:
        resp = await client.get("/api/v1/status")
    assert resp.status_code == 200
    data = resp.json()
    assert "active_memories" in data
    assert "total_interactions" in data


@pytest.mark.asyncio
async def test_ingest_validation():
    """POST /api/v1/ingest validates required fields."""
    async with _client() as client:
        resp = await client.post("/api/v1/ingest", json={})
    assert resp.status_code == 422
