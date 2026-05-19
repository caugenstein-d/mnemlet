"""Shared test fixtures."""

import tempfile
from pathlib import Path
import pytest
from mnemlet.storage.sqlite import MnemletDB
from mnemlet.storage.chroma import MnemletChroma
from mnemlet.storage.embeddings import MnemletEmbedding
from mnemlet.engine.ingest import IngestEngine
from mnemlet.engine.recall import RecallEngine


@pytest.fixture(scope="session")
def embedder():
    """Session-scoped embedding model (expensive to load)."""
    return MnemletEmbedding()
