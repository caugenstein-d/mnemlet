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
