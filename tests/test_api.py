"""Integration tests for the REST API."""

import tempfile
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from memoria.server.app import create_app
from memoria.config import MemoriaConfig


@pytest.fixture
async def client():
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        config = MemoriaConfig(
            data_dir=base,
            sqlite_path=base / "memoria.db",
            chroma_path=base / "chroma",
            embedding_cache_dir=base / "models",
        )
        app = create_app(config)
        async with app.router.lifespan_context(app):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                yield ac


@pytest.mark.asyncio
async def test_health_endpoint(client):
    """GET /api/v1/health returns 200."""
    resp = await client.get("/api/v1/health")
    assert resp.status_code == 200
    assert resp.json()["status"] == "ok"


@pytest.mark.asyncio
async def test_ingest_and_recall(client):
    """Full ingest → recall roundtrip."""
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
async def test_status_endpoint(client):
    """GET /api/v1/status returns memory counts."""
    resp = await client.get("/api/v1/status")
    assert resp.status_code == 200
    data = resp.json()
    assert "active_memories" in data
    assert "total_interactions" in data


@pytest.mark.asyncio
async def test_ingest_validation(client):
    """POST /api/v1/ingest validates required fields."""
    resp = await client.post("/api/v1/ingest", json={})
    assert resp.status_code == 422
