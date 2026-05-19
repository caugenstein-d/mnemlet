"""Tests for ChromaDB vector storage."""

import tempfile
from pathlib import Path
import pytest
from mnemlet.storage.chroma import MnemletChroma
from mnemlet.storage.embeddings import MnemletEmbedding


@pytest.fixture(scope="module")
def embedder():
    return MnemletEmbedding()


@pytest.fixture
def chroma(embedder):
    with tempfile.TemporaryDirectory() as tmpdir:
        client = MnemletChroma(Path(tmpdir), embedder)
        yield client


def test_store_and_query(chroma):
    """Store a document and query it back."""
    chroma.add(
        doc_id="doc-1",
        text="User prefers dark mode in all editors",
        metadata={"namespace": "preferences", "score": 0.8},
    )
    results = chroma.query("dark mode", n_results=3)
    assert len(results["ids"][0]) >= 1


def test_query_empty(chroma):
    """Query on empty collection returns empty results."""
    results = chroma.query("nothing here", n_results=5)
    assert len(results["ids"][0]) == 0


def test_delete(chroma):
    """Documents can be deleted."""
    chroma.add(doc_id="del-1", text="Temporary memory")
    chroma.delete("del-1")
    results = chroma.query("Temporary memory", n_results=5)
    assert "del-1" not in results["ids"][0]
