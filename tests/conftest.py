"""Shared test fixtures."""

import tempfile
from pathlib import Path
import pytest
from engram.storage.sqlite import EngramDB
from engram.storage.chroma import EngramChroma
from engram.storage.embeddings import EngramEmbedding
from engram.engine.ingest import IngestEngine
from engram.engine.recall import RecallEngine


@pytest.fixture(scope="session")
def embedder():
    """Session-scoped embedding model (expensive to load)."""
    return EngramEmbedding()
