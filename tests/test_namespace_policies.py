"""Tests for v0.3 namespace policies."""

from __future__ import annotations

import tempfile
import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient

from mnemlet.config import MnemletConfig
from mnemlet.constants import MEMORY_STATUS_ACTIVE
from mnemlet.security.namespace_policies import NamespacePolicy, policy_value_bool
from mnemlet.server.app import create_app
from mnemlet.server.mcp_server import create_mcp_server
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
        after_first = client._transport.app.state.db.get_memory(memory_id)
        second = await client.post(f"/api/v1/forget/{memory_id}?confirm=true")

    assert first.status_code == 409
    assert "confirm=true" in str(first.json())
    assert after_first["status"] == MEMORY_STATUS_ACTIVE
    assert second.status_code == 200


@pytest.mark.asyncio
async def test_soft_ingest_policy_warns_but_allows() -> None:
    async with _client() as client:
        await client.put("/api/v1/namespaces/closed/policies/allow_ingest", json={"value": "false"})
        response = await client.post("/api/v1/ingest", json={"content": "Allowed with warning", "namespace": "closed"})
        audit = await client.get("/api/v1/audit", params={"namespace": "closed"})

    assert response.status_code == 200
    assert any(
        event["result"] == "warning" and event["details"].get("policy") == "allow_ingest"
        for event in audit.json()["events"]
    )


@pytest.mark.asyncio
async def test_unknown_policy_key_returns_client_error() -> None:
    async with _client() as client:
        response = await client.put("/api/v1/namespaces/default/policies/not_a_policy", json={"value": "true"})

    assert response.status_code == 400


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("policy_key", "bad_value"),
    [
        ("allow_ingest", "maybe"),
        ("allow_recall", "maybe"),
        ("confirm_before_forget", "maybe"),
        ("secret_guard_action", "drop"),
        ("max_memories", "-1"),
        ("max_memories", "many"),
    ],
)
async def test_invalid_policy_values_are_rejected_and_not_stored(policy_key: str, bad_value: str) -> None:
    async with _client() as client:
        response = await client.put(f"/api/v1/namespaces/default/policies/{policy_key}", json={"value": bad_value})
        policies = await client.get("/api/v1/namespaces/default/policies")

    assert response.status_code == 400
    assert policies.json()["policies"][policy_key] != bad_value


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ("policy_key", "valid_value"),
    [
        ("allow_ingest", "false"),
        ("allow_recall", "false"),
        ("confirm_before_forget", "true"),
        ("secret_guard_action", "warn"),
        ("secret_guard_action", "allow"),
        ("max_memories", "10"),
    ],
)
async def test_valid_policy_values_are_accepted(policy_key: str, valid_value: str) -> None:
    async with _client() as client:
        response = await client.put(f"/api/v1/namespaces/default/policies/{policy_key}", json={"value": valid_value})
        policies = await client.get("/api/v1/namespaces/default/policies")

    assert response.status_code == 200
    assert policies.json()["policies"][policy_key] == valid_value


def _tool_result_json(result: list[Any]) -> dict[str, Any]:
    text = result[0].text
    return json.loads(text)


@pytest.mark.asyncio
async def test_mcp_forget_can_confirm_protected_memory() -> None:
    async with _client() as client:
        app_state = client._transport.app.state
        mcp = create_mcp_server(app_state)
        remembered = _tool_result_json(
            await mcp.call_tool(
                "mnemlet_remember",
                {"content": "MCP protected", "namespace": "mcp-protected"},
            )
        )
        memory_id = remembered["memory_id"]
        app_state.db.set_namespace_policy("mcp-protected", "confirm_before_forget", "true")

        first = _tool_result_json(await mcp.call_tool("mnemlet_forget", {"memory_id": memory_id}))
        after_first = app_state.db.get_memory(memory_id)
        second = _tool_result_json(
            await mcp.call_tool("mnemlet_forget", {"memory_id": memory_id, "confirm": True})
        )

    assert first["requires_confirmation"] is True
    assert after_first["status"] == MEMORY_STATUS_ACTIVE
    assert second["status"] == "forgotten"
