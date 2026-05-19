"""Tests for the recall pipeline."""

import tempfile
from pathlib import Path
import pytest
from engram.storage.sqlite import EngramDB
from engram.storage.chroma import EngramChroma
from engram.storage.embeddings import EngramEmbedding
from engram.engine.ingest import IngestEngine
from engram.engine.recall import RecallEngine


@pytest.fixture(scope="module")
def embedder():
    return EngramEmbedding()


@pytest.fixture
def engine(embedder):
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        db = EngramDB(base / "test.db")
        chroma = EngramChroma(base / "chroma", embedder)
        ingest = IngestEngine(db=db, chroma=chroma, embedder=embedder)
        recall = RecallEngine(db=db, chroma=chroma, embedder=embedder)
        ingest.ingest("User prefers dark mode in editors", namespace="preferences", importance=0.9)
        ingest.ingest("Project uses Python 3.12 with uv", namespace="projects/mirofish")
        ingest.ingest("Use 4 spaces for indentation in Python", namespace="code_style")
        yield recall


def test_recall_finds_relevant(engine):
    """Recall finds relevant memories for a query."""
    results = engine.recall(query="dark mode editor", namespace="preferences", limit=5)
    assert len(results) > 0
    assert any("dark" in r["content"].lower() for r in results)


def test_recall_namespace_isolation(engine):
    """Recall respects namespace boundaries."""
    results = engine.recall(query="python spaces", namespace="code_style", limit=5)
    assert all(r["namespace"] == "code_style" for r in results)


def test_recall_limits_results(engine):
    """Recall limits results to requested count."""
    results = engine.recall(query="python", namespace="projects/mirofish", limit=1)
    assert len(results) <= 1


def test_recall_empty_result(engine):
    """Recall returns empty list for unmatched query (with min_score threshold)."""
    results = engine.recall(query="quantum physics neutrino", namespace="preferences", limit=5, min_score=0.3)
    assert len(results) == 0
