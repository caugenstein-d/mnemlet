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
    text = Path("docs/index.html").read_text()

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


def test_demo_sh_visible_curl_posts_include_content_type() -> None:
    """Visible curl POST commands in demo.sh must show Content-Type header.

    The demo prints human-readable curl commands before executing them.
    Those printed commands must be copy-paste-equivalent to the real call,
    which includes -H 'Content-Type: application/json'.
    """
    text = Path("scripts/demo.sh").read_text()

    for line in text.splitlines():
        stripped = line.strip()
        # Only check echo/printf lines that display a curl POST command
        if "curl" in stripped and "POST" in stripped and ("echo" in stripped or "printf" in stripped):
            assert "Content-Type" in stripped, (
                f"Visible curl POST command missing Content-Type header: {stripped}"
            )


def test_demo_cast_visible_curl_posts_include_content_type() -> None:
    """Visible curl POST commands in demo.cast must show Content-Type header.

    The asciicast must not contain misleading curl POST commands that omit
    the JSON Content-Type header a viewer would need to replicate the call.
    """
    import json as _json

    cast_text = Path("scripts/demo.cast").read_text()
    lines = cast_text.strip().splitlines()

    for line in lines[1:]:  # skip header line
        event = _json.loads(line)
        if len(event) < 3 or event[1] != "o":
            continue
        output: str = event[2]
        # Check each visible line in the terminal output
        for fragment in output.replace("\\r\\n", "\n").replace("\r\n", "\n").split("\n"):
            if "curl" in fragment and "POST" in fragment and "$" in fragment:
                assert "Content-Type" in fragment, (
                    f"demo.cast visible POST command missing Content-Type: {fragment.strip()}"
                )


def test_quickstart_does_not_pin_v0_2_0() -> None:
    """Quickstart install instructions must not pin @v0.2.0 while documenting v0.3 auth."""
    readme = Path("README.md").read_text()
    website = Path("docs/index.html").read_text()

    assert "@v0.2.0" not in readme, (
        "README.md still pins @v0.2.0 in install — misleading alongside v0.3 auth docs"
    )
    assert "@v0.2.0" not in website, (
        "docs/index.html still pins @v0.2.0 in install — misleading alongside v0.3 auth docs"
    )


def test_pypi_installation_documented() -> None:
    """PyPI installation is documented as the primary install method."""
    readme = Path("README.md").read_text()
    website = Path("docs/index.html").read_text()

    assert "pip install mnemlet" in readme, (
        "README.md should document 'pip install mnemlet' as primary install method"
    )
    assert "pip install mnemlet" in website, (
        "docs/index.html should document 'pip install mnemlet' as primary install method"
    )
    assert "pypi.org/project/mnemlet" in readme, (
        "README.md should link to PyPI project page"
    )
