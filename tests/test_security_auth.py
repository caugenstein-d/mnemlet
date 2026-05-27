"""Tests for v0.3 API-key auth helpers and config loading."""

from __future__ import annotations

import tempfile
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from mnemlet.config import MnemletConfig
from mnemlet.server.app import create_app
from mnemlet.security.auth import (
    AuthDecision,
    hash_key_identity,
    key_configured,
    new_api_key,
    validate_api_key,
)


def test_new_api_key_has_prefix_and_entropy() -> None:
    key = new_api_key()

    assert key.startswith("mnemlet_")
    assert len(key) >= 40
    assert key != new_api_key()


def test_hash_key_identity_never_returns_key() -> None:
    key = "mnemlet_abcdefghijklmnopqrstuvwxyz123456"

    identity = hash_key_identity(key)

    assert identity != key
    assert len(identity) == 8


def test_key_configured_handles_blank_values() -> None:
    assert key_configured("mnemlet_abc") is True
    assert key_configured("") is False
    assert key_configured("   ") is False
    assert key_configured(None) is False


def test_validate_api_key_allows_when_no_key_is_configured() -> None:
    decision = validate_api_key(configured_key=None, provided_key=None)

    assert decision == AuthDecision(allowed=True, authenticated=False, reason="auth_not_configured")


def test_validate_api_key_rejects_missing_or_wrong_key() -> None:
    configured = "mnemlet_correct_key_1234567890abcdef"

    assert validate_api_key(configured, None).allowed is False
    assert validate_api_key(configured, "wrong").allowed is False


def test_validate_api_key_accepts_exact_key() -> None:
    configured = "mnemlet_correct_key_1234567890abcdef"
    decision = validate_api_key(configured, configured)

    assert decision.allowed is True
    assert decision.authenticated is True
    assert decision.caller_identity == hash_key_identity(configured)


def test_config_loads_auth_from_toml(tmp_path: Path) -> None:
    config_path = tmp_path / "mnemlet.toml"
    config_path.write_text('[auth]\napi_key = "mnemlet_file_key_1234567890abcdef"\n')

    config = MnemletConfig.from_toml(str(config_path))

    assert config.api_key == "mnemlet_file_key_1234567890abcdef"


def test_env_api_key_overrides_file_key(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    config_path = tmp_path / "mnemlet.toml"
    config_path.write_text('[auth]\napi_key = "mnemlet_file_key_1234567890abcdef"\n')
    monkeypatch.setenv("MNEMLET_API_KEY", "mnemlet_env_key_1234567890abcdef")

    config = MnemletConfig.from_toml(str(config_path))

    assert config.api_key == "mnemlet_env_key_1234567890abcdef"


@asynccontextmanager
async def _auth_client(api_key: str | None) -> AsyncIterator[AsyncClient]:
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


class _CountingSleepEngine:
    """Sleep engine test double that tracks activity bumps."""

    def __init__(self) -> None:
        self.bump_count = 0

    def bump_activity(self) -> None:
        self.bump_count += 1


@pytest.mark.asyncio
async def test_rest_allows_without_configured_key() -> None:
    async with _auth_client(api_key=None) as client:
        response = await client.get("/api/v1/health")

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_rest_rejects_missing_key_when_configured() -> None:
    async with _auth_client(api_key="mnemlet_rest_key_1234567890abcdef") as client:
        response = await client.get("/api/v1/status")

    assert response.status_code == 401
    assert response.json()["detail"] == "Unauthorized"


@pytest.mark.asyncio
async def test_rest_accepts_x_mnemlet_key_header() -> None:
    key = "mnemlet_rest_key_1234567890abcdef"
    async with _auth_client(api_key=key) as client:
        response = await client.get("/api/v1/status", headers={"X-Mnemlet-Key": key})

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_rest_accepts_bearer_header() -> None:
    key = "mnemlet_rest_key_1234567890abcdef"
    async with _auth_client(api_key=key) as client:
        response = await client.get("/api/v1/status", headers={"Authorization": f"Bearer {key}"})

    assert response.status_code == 200


@pytest.mark.asyncio
async def test_rest_rejects_wrong_key() -> None:
    async with _auth_client(api_key="mnemlet_rest_key_1234567890abcdef") as client:
        response = await client.get("/api/v1/status", headers={"X-Mnemlet-Key": "wrong"})

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_rejected_rest_auth_does_not_bump_activity() -> None:
    key = "mnemlet_rest_key_1234567890abcdef"
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        config = MnemletConfig(
            data_dir=base,
            sqlite_path=base / "mnemlet.db",
            chroma_path=base / "chroma",
            vault_path=base / "vault",
            embedding_cache_dir=base / "models",
            api_key=key,
        )
        app = create_app(config)
        async with app.router.lifespan_context(app):
            sleep_engine = _CountingSleepEngine()
            app.state.sleep_engine = sleep_engine
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                missing_response = await client.get("/api/v1/status")
                wrong_response = await client.get(
                    "/api/v1/status",
                    headers={"X-Mnemlet-Key": "wrong"},
                )

    assert missing_response.status_code == 401
    assert wrong_response.status_code == 401
    assert sleep_engine.bump_count == 0


@pytest.mark.asyncio
async def test_auth_middleware_protects_mcp_mount() -> None:
    async with _auth_client(api_key="mnemlet_rest_key_1234567890abcdef") as client:
        response = await client.post("/mcp", content=b"")

    assert response.status_code == 401


@pytest.mark.asyncio
async def test_mcp_mount_accepts_configured_key_before_body_validation() -> None:
    key = "mnemlet_rest_key_1234567890abcdef"
    async with _auth_client(api_key=key) as client:
        response = await client.post("/mcp", headers={"X-Mnemlet-Key": key}, content=b"")

    assert response.status_code != 401
