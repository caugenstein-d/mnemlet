"""Tests for Context Pack REST API."""

import tempfile
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from mnemlet.config import MnemletConfig
from mnemlet.server.app import create_app


@asynccontextmanager
async def _client() -> AsyncIterator[AsyncClient]:
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
async def test_context_endpoint_returns_context_pack() -> None:
    async with _client() as client:
        await client.post(
            "/api/v1/ingest",
            json={"content": "Christoph prefers self-hosted tools", "namespace": "prefs", "importance": 0.9},
        )

        resp = await client.post(
            "/api/v1/context",
            json={"query": "self hosted tools", "namespace": "prefs", "limit": 5},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["query"] == "self hosted tools"
    assert set(data["context_pack"]) == {"primary", "supporting", "superseded"}
    assert data["meta"]["total_candidates"] >= 1


@pytest.mark.asyncio
async def test_context_endpoint_abstains_without_results() -> None:
    async with _client() as client:
        resp = await client.post(
            "/api/v1/context",
            json={"query": "unknown nebula", "namespace": "empty", "limit": 5, "min_score": 0.3},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["context_pack"] == {"primary": [], "supporting": [], "superseded": []}
    assert data["abstention"]["reason"] == "no_relevant_memories"
