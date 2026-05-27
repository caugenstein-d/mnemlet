"""Tests for startup security checks and status truth."""

from __future__ import annotations

import os
import stat
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from mnemlet.config import MnemletConfig
from mnemlet.security.startup_check import SecurityCheck, run_startup_security_checks
from mnemlet.server.app import create_app


def _config(base: Path, *, host: str = "127.0.0.1", api_key: str | None = None) -> MnemletConfig:
    """Build a test config rooted in a temporary directory."""
    return MnemletConfig(
        server_host=host,
        data_dir=base,
        sqlite_path=base / "mnemlet.db",
        chroma_path=base / "chroma",
        vault_path=base / "vault",
        embedding_cache_dir=base / "models",
        api_key=api_key,
    )


@asynccontextmanager
async def _client(config: MnemletConfig) -> AsyncIterator[AsyncClient]:
    """Create an isolated API client with app lifespan in the test task."""
    app = create_app(config)
    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            yield client


def test_startup_check_warns_for_public_host(tmp_path: Path) -> None:
    """Startup checks warn when the server binds to all interfaces."""
    checks = run_startup_security_checks(_config(tmp_path, host="0.0.0.0"))

    assert SecurityCheck("public_host", "warning", "server is bound to 0.0.0.0") in checks


def test_startup_check_warns_when_auth_missing(tmp_path: Path) -> None:
    """Startup checks warn when API-key auth is absent."""
    checks = run_startup_security_checks(_config(tmp_path, api_key=None))

    assert any(c.code == "auth_missing" and c.level == "warning" for c in checks)


def test_startup_check_warns_for_world_readable_db(tmp_path: Path) -> None:
    """Startup checks warn when private storage paths are world-readable."""
    db_path = tmp_path / "mnemlet.db"
    db_path.write_text("placeholder")
    os.chmod(db_path, stat.S_IRUSR | stat.S_IWUSR | stat.S_IROTH)

    checks = run_startup_security_checks(_config(tmp_path))

    assert any(c.code == "unsafe_permissions" and "mnemlet.db" in c.message for c in checks)


def test_config_defaults_to_local_cors_origins() -> None:
    """Config defaults CORS to local browser origins only."""
    cfg = MnemletConfig()

    assert cfg.cors_origins == ["http://localhost", "http://127.0.0.1"]


def test_config_loads_cors_origins_from_toml(tmp_path: Path) -> None:
    """Config loads explicit CORS origins from TOML."""
    config_path = tmp_path / "mnemlet.toml"
    config_path.write_text('[server]\ncors_origins = ["http://app.local"]\n')

    cfg = MnemletConfig.from_toml(str(config_path))

    assert cfg.cors_origins == ["http://app.local"]


def test_startup_check_warns_when_any_cors_origin_is_wildcard(tmp_path: Path) -> None:
    """Startup checks warn when any configured CORS origin allows all origins."""
    config = _config(tmp_path)
    config.cors_origins = ["*", "http://app.local"]

    checks = run_startup_security_checks(config)

    assert any(c.code == "cors_wildcard" and c.level == "warning" for c in checks)


@pytest.mark.asyncio
async def test_status_exposes_auth_and_security_warnings(tmp_path: Path) -> None:
    """Status reports auth state and startup security warnings."""
    async with _client(_config(tmp_path, api_key=None)) as client:
        response = await client.get("/api/v1/status")

    assert response.status_code == 200
    payload = response.json()
    assert payload["security"]["auth_configured"] is False
    assert any(w["code"] == "auth_missing" for w in payload["security"]["warnings"])


@pytest.mark.asyncio
async def test_status_reports_auth_configured(tmp_path: Path) -> None:
    """Status reports when API-key auth is configured."""
    async with _client(_config(tmp_path, api_key="mnemlet_test_key_1234567890abcdef")) as client:
        response = await client.get("/api/v1/status")

    assert response.status_code == 200
    assert response.json()["security"]["auth_configured"] is True
