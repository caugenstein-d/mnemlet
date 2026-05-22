"""Tests for the recall pipeline."""

import tempfile
from pathlib import Path
import pytest
from mnemlet.storage.sqlite import MnemletDB
from mnemlet.storage.chroma import MnemletChroma
from mnemlet.storage.embeddings import MnemletEmbedding
from mnemlet.engine.ingest import IngestEngine
from mnemlet.engine.recall import RecallEngine


@pytest.fixture(scope="module")
def embedder():
    return MnemletEmbedding()


@pytest.fixture
def engine(embedder):
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        db = MnemletDB(base / "test.db")
        chroma = MnemletChroma(base / "chroma", embedder)
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


def test_recall_excludes_superseded_memories_by_default(embedder):
    """Legacy recall must not return superseded memories as active facts."""
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        db = MnemletDB(base / "test.db")
        chroma = MnemletChroma(base / "chroma", embedder)
        ingest = IngestEngine(db=db, chroma=chroma, embedder=embedder)
        recall = RecallEngine(db=db, chroma=chroma, embedder=embedder)

        old = ingest.ingest("The service runs on port 8080", namespace="infra")
        ingest.ingest("The service runs on port 9090", namespace="infra")
        db.update_memory_status(str(old["memory_id"]), "superseded")

        results = recall.recall("What port does the service run on?", namespace="infra", limit=5)

        assert all(item["id"] != old["memory_id"] for item in results)
        assert all(item["status"] == "active" for item in results)


def test_recall_includes_minimal_provenance(embedder):
    """Legacy recall results expose additive provenance without breaking content/score."""
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        db = MnemletDB(base / "test.db")
        chroma = MnemletChroma(base / "chroma", embedder)
        ingest = IngestEngine(db=db, chroma=chroma, embedder=embedder)
        recall = RecallEngine(db=db, chroma=chroma, embedder=embedder)

        ingest.ingest("Christoph prefers self-hosted tools", namespace="preferences")

        results = recall.recall("self hosted tools", namespace="preferences", limit=5)

        assert results
        first = results[0]
        assert first["content"]
        assert first["score"] >= 0
        assert first["namespace"] == "preferences"
        assert first["source"] in {"vector", "fts", "hybrid"}
        assert first["rank"] == 1
        assert first["status"] == "active"
        assert "created_at" in first
        assert "access_count" in first
