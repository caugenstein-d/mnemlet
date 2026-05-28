"""Tests for the read-only web dashboard: shell serving, auth exemption,
the new /memories endpoints, status enrichment, and audit pagination."""

from __future__ import annotations

import tempfile
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from mnemlet.config import MnemletConfig
from mnemlet.security.startup_check import run_startup_security_checks
from mnemlet.server.app import create_app


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


async def _ingest(client: AsyncClient, content: str, namespace: str, headers=None) -> str:
    resp = await client.post(
        "/api/v1/ingest",
        json={"content": content, "namespace": namespace, "importance": 0.9},
        headers=headers or {},
    )
    assert resp.status_code == 200, resp.text
    mid = resp.json()["memory_id"]
    return mid if isinstance(mid, str) else mid[0]


# ──────────────────────────── UI shell + auth ────────────────────────────


@pytest.mark.asyncio
async def test_ui_shell_served_without_auth_even_when_key_configured() -> None:
    """The dashboard shell must load without a key so the login dialog can render."""
    async with _client(api_key="mnemlet_dash_key_1234567890abcdef") as client:
        resp = await client.get("/ui")
    assert resp.status_code == 200
    assert "text/html" in resp.headers["content-type"]
    assert "dashboard()" in resp.text
    assert "max-age=3600" in resp.headers.get("cache-control", "")


@pytest.mark.asyncio
async def test_ui_catch_all_serves_same_shell() -> None:
    """Every client-routed /ui path returns the same shell (SPA fallback)."""
    async with _client() as client:
        for path in ("/ui/memories", "/ui/audit", "/ui/memory/abc123"):
            resp = await client.get(path)
            assert resp.status_code == 200, path
            assert "dashboard()" in resp.text


@pytest.mark.asyncio
async def test_api_still_requires_auth_when_configured() -> None:
    """The /ui exemption must not leak to the data endpoints."""
    async with _client(api_key="mnemlet_dash_key_1234567890abcdef") as client:
        resp = await client.get("/api/v1/memories")
    assert resp.status_code == 401


# ──────────────────────────── memories list ────────────────────────────


@pytest.mark.asyncio
async def test_memories_list_pagination_and_namespaces() -> None:
    async with _client() as client:
        await _ingest(client, "I prefer dark mode", "preferences")
        await _ingest(client, "Project uses Python 3.12", "projects")
        await _ingest(client, "Likes tabs over spaces", "preferences")

        resp = await client.get("/api/v1/memories?limit=2&offset=0")
        assert resp.status_code == 200
        data = resp.json()
        assert data["total"] == 3
        assert len(data["memories"]) == 2
        assert data["limit"] == 2
        assert set(data["namespaces"]) == {"preferences", "projects"}

        page2 = await client.get("/api/v1/memories?limit=2&offset=2")
        assert len(page2.json()["memories"]) == 1


@pytest.mark.asyncio
async def test_memories_list_namespace_filter() -> None:
    async with _client() as client:
        await _ingest(client, "I prefer dark mode", "preferences")
        await _ingest(client, "Project uses Python", "projects")

        resp = await client.get("/api/v1/memories?namespace=preferences")
        data = resp.json()
        assert data["total"] == 1
        assert all(m["namespace"] == "preferences" for m in data["memories"])


# ──────────────────────────── memory detail ────────────────────────────


@pytest.mark.asyncio
async def test_memory_detail_returns_content_frontmatter_trust_and_path() -> None:
    async with _client() as client:
        content = "I strongly prefer dark mode in every editor I use."
        mid = await _ingest(client, content, "preferences")

        resp = await client.get(f"/api/v1/memories/{mid}")
        assert resp.status_code == 200
        data = resp.json()
        assert data["id"] == mid
        assert data["content"].strip() == content
        assert "namespace: preferences" in data["frontmatter"]
        assert data["trust"]["ingested_by"]  # populated, not empty
        assert data["trust"]["secret_guard_result"] == "clean"
        assert data["file"]["exists"] is True
        assert "vault" in data["file"]["display_path"]


@pytest.mark.asyncio
async def test_memory_detail_404_for_unknown_id() -> None:
    async with _client() as client:
        resp = await client.get("/api/v1/memories/does-not-exist")
    assert resp.status_code == 404


# ──────────────────────────── status enrichment ────────────────────────────


@pytest.mark.asyncio
async def test_status_includes_total_and_decay_histogram() -> None:
    async with _client() as client:
        await _ingest(client, "I prefer dark mode", "preferences")

        resp = await client.get("/api/v1/status")
        data = resp.json()
        assert data["total_memories"] == 1
        hist = data["decay_distribution"]
        assert len(hist) == 5
        assert sum(b["count"] for b in hist) == 1
        assert all("label" in b and "count" in b for b in hist)


@pytest.mark.asyncio
async def test_status_includes_intelligence_block_default_off() -> None:
    async with _client() as client:
        data = (await client.get("/api/v1/status")).json()
    intel = data["intelligence"]
    assert intel["llm_enabled"] is False
    assert intel["extraction_active"] is False
    assert intel["llm_model"] is None


@pytest.mark.asyncio
async def test_status_reports_extraction_active_when_enabled() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        config = MnemletConfig(
            data_dir=base,
            sqlite_path=base / "mnemlet.db",
            chroma_path=base / "chroma",
            vault_path=base / "vault",
            embedding_cache_dir=base / "models",
            llm_enabled=True,
            extraction_enabled=True,
            llm_model="gemma3:4b",
        )
        app = create_app(config)
        async with app.router.lifespan_context(app):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                data = (await client.get("/api/v1/status")).json()
    intel = data["intelligence"]
    assert intel["llm_enabled"] is True
    assert intel["extraction_active"] is True
    assert intel["llm_model"] == "gemma3:4b"


# ──────────────────────────── audit pagination ────────────────────────────


@pytest.mark.asyncio
async def test_audit_supports_result_filter_and_pagination_total() -> None:
    async with _client() as client:
        await _ingest(client, "I prefer dark mode", "preferences")

        resp = await client.get("/api/v1/audit?limit=1&offset=0&result=success")
        assert resp.status_code == 200
        data = resp.json()
        assert "total" in data and data["total"] >= 1
        assert data["limit"] == 1
        assert all(e["result"] == "success" for e in data["events"])


# ──────────────────────────── sleep decoupling ────────────────────────────


class _CountingSleepEngine:
    def __init__(self) -> None:
        self.bump_count = 0

    def bump_activity(self) -> None:
        self.bump_count += 1


@pytest.mark.asyncio
async def test_ui_poll_header_does_not_bump_sleep_activity() -> None:
    """Read-only dashboard polls must not keep the sleep engine awake."""
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
            counter = _CountingSleepEngine()
            app.state.sleep_engine = counter
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                await client.get("/api/v1/status", headers={"X-Mnemlet-UI": "1"})
                assert counter.bump_count == 0
                await client.get("/api/v1/status")
                assert counter.bump_count == 1


# ──────────────────────────── startup check ────────────────────────────


def test_startup_check_flags_network_exposed_without_auth(tmp_path: Path) -> None:
    config = MnemletConfig(
        server_host="0.0.0.0",
        data_dir=tmp_path,
        sqlite_path=tmp_path / "mnemlet.db",
        vault_path=tmp_path / "vault",
        api_key=None,
    )
    checks = run_startup_security_checks(config)
    assert any(c.code == "network_exposed" and c.level == "critical" for c in checks)


def test_startup_check_no_network_exposed_when_auth_present(tmp_path: Path) -> None:
    config = MnemletConfig(
        server_host="0.0.0.0",
        data_dir=tmp_path,
        sqlite_path=tmp_path / "mnemlet.db",
        vault_path=tmp_path / "vault",
        api_key="mnemlet_dash_key_1234567890abcdef",
    )
    checks = run_startup_security_checks(config)
    assert not any(c.code == "network_exposed" for c in checks)
