"""Shared test fixtures."""

import tempfile
from pathlib import Path
import pytest
from memoria.storage.sqlite import MemoriaDB
from memoria.storage.chroma import MemoriaChroma
from memoria.storage.embeddings import MemoriaEmbedding
from memoria.engine.ingest import IngestEngine
from memoria.engine.recall import RecallEngine


@pytest.fixture(scope="session")
def embedder():
    """Session-scoped embedding model (expensive to load)."""
    return MemoriaEmbedding()
