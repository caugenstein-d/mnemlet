"""Tests for v0.3 API-key auth helpers and config loading."""

from __future__ import annotations

from pathlib import Path

import pytest

from mnemlet.config import MnemletConfig
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
