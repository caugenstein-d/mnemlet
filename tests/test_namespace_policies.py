"""Tests for v0.3 namespace policies."""

from __future__ import annotations

import tempfile
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from mnemlet.config import MnemletConfig
from mnemlet.security.namespace_policies import NamespacePolicy, policy_value_bool
from mnemlet.server.app import create_app
from mnemlet.storage.sqlite import MnemletDB


def test_namespace_policy_schema_and_defaults(tmp_path: Path) -> None:
    db = MnemletDB(tmp_path / "mnemlet.db")
    try:
        assert "namespace_policies" in db._list_tables()
        assert db.get_namespace_policy("preferences", "allow_ingest") == "true"
    finally:
        db.close()


def test_policy_value_bool() -> None:
    assert policy_value_bool("true") is True
    assert policy_value_bool("false") is False


def test_namespace_policy_dataclass() -> None:
    policy = NamespacePolicy("ops", "allow_recall", "false")

    assert policy.namespace == "ops"
    assert policy.policy_key == "allow_recall"
    assert policy.policy_value == "false"


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
async def test_confirm_before_forget_requires_confirmation() -> None:
    async with _client() as client:
        remembered = await client.post("/api/v1/remember", json={"content": "Keep this", "namespace": "protected"})
        memory_id = remembered.json()["memory_id"]
        await client.put("/api/v1/namespaces/protected/policies/confirm_before_forget", json={"value": "true"})

        first = await client.post(f"/api/v1/forget/{memory_id}")
        second = await client.post(f"/api/v1/forget/{memory_id}?confirm=true")

    assert first.status_code == 409
    assert "confirm=true" in str(first.json())
    assert second.status_code == 200


@pytest.mark.asyncio
async def test_soft_ingest_policy_warns_but_allows() -> None:
    async with _client() as client:
        await client.put("/api/v1/namespaces/closed/policies/allow_ingest", json={"value": "false"})
        response = await client.post("/api/v1/ingest", json={"content": "Allowed with warning", "namespace": "closed"})
        audit = await client.get("/api/v1/audit", params={"namespace": "closed"})

    assert response.status_code == 200
    assert any(event["result"] == "warning" for event in audit.json()["events"])
