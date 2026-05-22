"""Tests for the ingest pipeline."""

import tempfile
from pathlib import Path
import pytest
from mnemlet.storage.sqlite import MnemletDB
from mnemlet.storage.chroma import MnemletChroma
from mnemlet.storage.embeddings import MnemletEmbedding
from mnemlet.engine.ingest import IngestEngine


@pytest.fixture(scope="module")
def embedder():
    return MnemletEmbedding()


@pytest.fixture
def engine(embedder):
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        db = MnemletDB(base / "test.db")
        chroma = MnemletChroma(base / "chroma", embedder)
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


def test_ingest_classifies_memory_heuristically(engine):
    """New memories receive a deterministic MVP memory type."""
    result = engine.ingest(
        content="Christoph bevorzugt Self-Hosting für Agent Memory",
        namespace="preferences",
        importance=0.8,
    )

    memory = engine.db.get_memory(result["memory_id"])

    assert memory["memory_type"] == "preference"
    assert memory["type_source"] == "heuristic"
    assert memory["type_confidence"] >= 0.7
