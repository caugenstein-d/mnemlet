"""Tests for the Python SDK client."""


def test_client_import():
    """Client module is importable."""
    from engram.client import EngramClient

    assert EngramClient is not None


def test_client_default_url():
    """Client has sensible defaults."""
    from engram.client import EngramClient

    c = EngramClient()
    assert c.base_url == "http://localhost:4050"


def test_client_context_manager():
    """Client works as context manager."""
    from engram.client import EngramClient

    with EngramClient() as c:
        assert c is not None
