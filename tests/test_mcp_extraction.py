"""Tests for v0.4 config, app wiring, and the MCP observe tool."""

import json
import tempfile
from pathlib import Path
from typing import Any

import pytest

from mnemlet.config import MnemletConfig
from mnemlet.intelligence.pipeline import ExtractionPipeline
from mnemlet.server.app import create_app
from mnemlet.server.mcp_server import create_mcp_server


def _config(base: Path, **overrides) -> MnemletConfig:
    return MnemletConfig(
        data_dir=base,
        sqlite_path=base / "mnemlet.db",
        chroma_path=base / "chroma",
        vault_path=base / "vault",
        embedding_cache_dir=base / "models",
        **overrides,
    )


def _tool_json(result: list[Any]) -> dict:
    return json.loads(result[0].text)


# ──────────────────────────── config ────────────────────────────


def test_config_loads_llm_and_intelligence_from_toml(tmp_path: Path) -> None:
    cfg_path = tmp_path / "mnemlet.toml"
    cfg_path.write_text(
        "[llm]\nenabled = true\nmodel = \"gemma3:4b\"\nbase_url = \"http://pi:11434\"\n\n"
        "[intelligence]\nextraction_enabled = true\nextract_memories = false\n"
        "inactivity_threshold_minutes = 5\nmax_messages = 42\n"
    )

    cfg = MnemletConfig.from_toml(str(cfg_path))

    assert cfg.llm_enabled is True
    assert cfg.llm_model == "gemma3:4b"
    assert cfg.llm_base_url == "http://pi:11434"
    assert cfg.extraction_enabled is True
    assert cfg.extract_memories is False
    assert cfg.inactivity_threshold_minutes == 5
    assert cfg.max_buffer_messages == 42


def test_config_defaults_keep_extraction_off() -> None:
    cfg = MnemletConfig()
    assert cfg.llm_enabled is False
    assert cfg.extraction_enabled is False


def test_env_can_force_enable(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("MNEMLET_LLM_ENABLED", "1")
    monkeypatch.setenv("MNEMLET_EXTRACTION_ENABLED", "true")
    cfg = MnemletConfig()
    assert cfg.llm_enabled is True
    assert cfg.extraction_enabled is True


# ──────────────────────────── app wiring ────────────────────────────


@pytest.mark.asyncio
async def test_app_has_no_pipeline_by_default() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        app = create_app(_config(Path(tmpdir)))
        async with app.router.lifespan_context(app):
            assert app.state.extraction_pipeline is None
            assert app.state.llm is None
            assert app.state.sleep_engine.llm is None


@pytest.mark.asyncio
async def test_app_builds_pipeline_when_enabled() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        config = _config(Path(tmpdir), llm_enabled=True, extraction_enabled=True)
        app = create_app(config)
        async with app.router.lifespan_context(app):
            assert isinstance(app.state.extraction_pipeline, ExtractionPipeline)
            assert app.state.llm is not None
            assert app.state.sleep_engine.llm is app.state.llm


@pytest.mark.asyncio
async def test_app_llm_without_extraction_powers_briefing_only() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        config = _config(Path(tmpdir), llm_enabled=True, extraction_enabled=False)
        app = create_app(config)
        async with app.router.lifespan_context(app):
            assert app.state.extraction_pipeline is None
            assert app.state.llm is not None
            assert app.state.sleep_engine.llm is app.state.llm


# ──────────────────────────── MCP observe tool ────────────────────────────


@pytest.mark.asyncio
async def test_observe_tool_registered() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        app = create_app(_config(Path(tmpdir)))
        async with app.router.lifespan_context(app):
            tools = await app.state.mcp_session_manager._mcp_server.list_tools()
    assert any(getattr(t, "name", "") == "mnemlet_observe" for t in tools)


@pytest.mark.asyncio
async def test_observe_buffers_when_extraction_enabled() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        config = _config(Path(tmpdir), llm_enabled=True, extraction_enabled=True)
        app = create_app(config)
        async with app.router.lifespan_context(app):
            mcp = create_mcp_server(app.state)
            result = _tool_json(
                await mcp.call_tool(
                    "mnemlet_observe",
                    {"content": "I prefer dark mode", "session_id": "s1", "namespace": "prefs"},
                )
            )
            assert result["buffered"] is True
            assert result["session_id"] == "s1"
            # message landed in the buffer (no LLM/flush triggered)
            assert "s1" in app.state.extraction_pipeline.buffer._buffers


@pytest.mark.asyncio
async def test_observe_advises_when_extraction_disabled() -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        app = create_app(_config(Path(tmpdir)))
        async with app.router.lifespan_context(app):
            mcp = create_mcp_server(app.state)
            result = _tool_json(
                await mcp.call_tool("mnemlet_observe", {"content": "hi"})
            )
    assert result["buffered"] is False
    assert "mnemlet_ingest" in result["note"]
