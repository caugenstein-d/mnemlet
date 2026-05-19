"""Tests for the ingest pipeline."""

import tempfile
from pathlib import Path
import pytest
from engram.storage.sqlite import EngramDB
from engram.storage.chroma import EngramChroma
from engram.storage.embeddings import EngramEmbedding
from engram.engine.ingest import IngestEngine


@pytest.fixture(scope="module")
def embedder():
    return EngramEmbedding()


@pytest.fixture
def engine(embedder):
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        db = EngramDB(base / "test.db")
        chroma = EngramChroma(base / "chroma", embedder)
        eng = IngestEngine(db=db, chroma=chroma, embedder=embedder)
        yield eng


def test_ingest_single_memory(engine):
    """Ingest a single memory and verify it's stored."""
    result = engine.ingest(
        content="User prefers dark mode in all editors",
        namespace="preferences",
        importance=0.9,
    )
    assert result["memory_id"] is not None
    assert result["stored"] is True
    assert result["namespace"] == "preferences"
    assert result["retention_score"] == pytest.approx(0.45)  # 0.9 * 0.5


def test_ingest_deduplicates(engine):
    """Ingesting duplicate content returns existing memory."""
    first = engine.ingest(
        content="Use 4 spaces for indentation",
        namespace="code_style",
    )
    second = engine.ingest(
        content="Use 4 spaces for indentation",
        namespace="code_style",
    )
    assert second["stored"] is False
    assert second["memory_id"] == first["memory_id"]


def test_ingest_long_content_is_chunked(engine):
    """Content over the token limit is chunked."""
    long_text = "This is a long text. " * 600  # >> 3000 tokens (chars // 4 = 3300)
    result = engine.ingest(
        content=long_text,
        namespace="test",
    )
    assert result["chunk_count"] >= 2
