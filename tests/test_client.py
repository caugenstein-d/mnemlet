"""Tests for the Python SDK client."""


def test_client_import():
    """Client module is importable."""
    from memoria.client import MemoriaClient

    assert MemoriaClient is not None


def test_client_default_url():
    """Client has sensible defaults."""
    from memoria.client import MemoriaClient

    c = MemoriaClient()
    assert c.base_url == "http://localhost:4050"


def test_client_context_manager():
    """Client works as context manager."""
    from memoria.client import MemoriaClient

    with MemoriaClient() as c:
        assert c is not None
