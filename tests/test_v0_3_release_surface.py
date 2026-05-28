"""Tests for v0.3 public release documentation surface."""

from __future__ import annotations

from pathlib import Path


def test_readme_mentions_v0_3_auth_and_secret_guard() -> None:
    """README documents v0.3 auth, Secret Guard, and audit behavior."""
    text = Path("README.md").read_text()

    assert "X-Mnemlet-Key" in text
    assert "Secret Guard" in text
    assert "Audit" in text
    assert "There is no authentication layer yet" not in text
    assert "PyPI release follows once the Trust/Security/Privacy layer lands in v0.3." not in text


def test_security_md_matches_v0_3_behavior() -> None:
    """Security policy documents v0.3 API-key deployment guidance."""
    text = Path("SECURITY.md").read_text()

    assert "API key" in text
    assert "Do not expose" in text


def test_demo_uses_throwaway_auth_and_audit_flow() -> None:
    """Demo script uses throwaway auth and avoids the production daemon."""
    text = Path("scripts/demo.sh").read_text()

    assert "MNEMLET_API_KEY" in text
    assert "X-Mnemlet-Key" in text
    assert "/api/v1/audit" in text
    assert "127.0.0.1:4050" not in text


def test_website_demo_matches_v0_3_secret_guard_runtime_shape() -> None:
    """Website demo mirrors the real Secret Guard and audit response shape."""
    text = Path("website/index.html").read_text()

    assert "sk-aaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaaa" in text
    assert "Content-Type: application/json" in text
    assert "secret_guard_blocked: patterns=openai_key" in text
    assert "sk-test..." not in text
    assert '"action":"remember"' not in text
    assert '{"events":[{"action":"ingest","result":"blocked"},{"action":"ingest","result":"success"}]}' in text


def test_readme_marks_python_sdk_as_no_key_development_only() -> None:
    """README does not imply the current Python SDK sends auth headers."""
    text = Path("README.md").read_text()

    assert "Python SDK example is for localhost no-key development only" in text
    assert "Authenticated server mode currently needs REST or MCP with `X-Mnemlet-Key`." in text
