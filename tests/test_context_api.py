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


@pytest.mark.asyncio
@pytest.mark.parametrize(
    "payload",
    [
        {"query": "", "namespace": "prefs", "limit": 5},
        {"query": "valid", "namespace": "prefs", "limit": 0},
        {"query": "valid", "namespace": "prefs", "limit": 11},
        {"query": "valid", "namespace": "prefs", "limit": 5, "min_score": -0.1},
        {"query": "valid", "namespace": "prefs", "limit": 5, "min_score": 1.5},
    ],
)
async def test_context_endpoint_rejects_invalid_bounds(payload: dict) -> None:
    async with _client() as client:
        resp = await client.post("/api/v1/context", json=payload)

    assert resp.status_code == 422, (
        f"expected 422 for payload {payload!r}, got {resp.status_code}: {resp.text}"
    )


@pytest.mark.asyncio
async def test_context_endpoint_include_superseded_toggle() -> None:
    async with _client() as client:
        ingest_resp = await client.post(
            "/api/v1/ingest",
            json={
                "content": "Christoph prefers self-hosted tools",
                "namespace": "prefs",
                "importance": 0.9,
            },
        )
        assert ingest_resp.status_code == 200
        memory_id = ingest_resp.json()["memory_id"]

        # Mark the memory as superseded via direct DB access on the running app.
        db = client._transport.app.state.db
        updated = db.update_memory_status(memory_id, "superseded")
        assert updated is not None and updated["status"] == "superseded"

        included = await client.post(
            "/api/v1/context",
            json={
                "query": "self hosted tools",
                "namespace": "prefs",
                "limit": 5,
                "include_superseded": True,
            },
        )
        excluded = await client.post(
            "/api/v1/context",
            json={
                "query": "self hosted tools",
                "namespace": "prefs",
                "limit": 5,
            },
        )

    assert included.status_code == 200
    included_data = included.json()
    superseded_ids = [item["id"] for item in included_data["context_pack"]["superseded"]]
    assert memory_id in superseded_ids

    assert excluded.status_code == 200
    excluded_data = excluded.json()
    assert excluded_data["context_pack"]["superseded"] == []


@pytest.mark.asyncio
async def test_review_and_explain_routes_roundtrip() -> None:
    async with _client() as client:
        remember = await client.post(
            "/api/v1/remember",
            json={"content": "OpenWebUI darf nicht restarted werden", "namespace": "ops", "importance": 0.9, "memory_type": "instruction"},
        )
        memory_id = remember.json()["memory_id"]

        confirm = await client.post(f"/api/v1/confirm/{memory_id}")
        explain = await client.get(f"/api/v1/explain/{memory_id}")
        forget = await client.post(f"/api/v1/forget/{memory_id}")

    assert remember.status_code == 200
    assert confirm.status_code == 200
    assert explain.status_code == 200
    assert explain.json()["memory_type"] == "instruction"
    assert forget.status_code == 200
    assert forget.json()["status"] == "forgotten"
