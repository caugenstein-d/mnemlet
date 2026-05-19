"""Tests for the Python SDK client."""


def test_client_import():
    """Client module is importable."""
    from mnemlet.client import MnemletClient

    assert MnemletClient is not None


def test_client_default_url():
    """Client has sensible defaults."""
    from mnemlet.client import MnemletClient

    c = MnemletClient()
    assert c.base_url == "http://localhost:4050"


def test_client_context_manager():
    """Client works as context manager."""
    from mnemlet.client import MnemletClient

    with MnemletClient() as c:
        assert c is not None
