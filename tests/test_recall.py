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


def test_merge_results_marks_hybrid_sources():
    """Overlapping vector and FTS hits are labeled hybrid without changing solo sources."""
    recall = RecallEngine(db=None, chroma=None, embedder=None)

    results = recall._merge_results(
        vector=[
            {"id": "both", "content": "shared", "score": 0.9, "namespace": "test"},
            {"id": "vector-only", "content": "vector", "score": 0.8, "namespace": "test"},
        ],
        fts=[
            {"id": "both", "content": "shared", "score": 0.5, "namespace": "test"},
            {"id": "fts-only", "content": "fts", "score": 0.5, "namespace": "test"},
        ],
        limit=10,
    )

    by_id = {item["id"]: item for item in results}
    assert by_id["both"]["source"] == "hybrid"
    assert by_id["vector-only"]["source"] == "vector"
    assert by_id["fts-only"]["source"] == "fts"


def test_recall_respects_explicit_empty_status_set(engine):
    """An explicit empty status set returns no memories instead of defaulting to active."""
    results = engine.recall(
        "dark mode editor",
        namespace="preferences",
        include_statuses=set(),
    )

    assert results == []


def test_recall_overfetches_when_superseded_candidates_crowd_active_results():
    """Recall fetches enough candidates before status filtering to avoid active starvation."""

    class FakeChroma:
        def __init__(self):
            self.docs = [
                {"id": f"old-{index}", "content": f"old memory {index}", "distance": 0.01 * index}
                for index in range(1, 5)
            ] + [
                {"id": "active-1", "content": "active memory 1", "distance": 0.50},
                {"id": "active-2", "content": "active memory 2", "distance": 0.51},
            ]

        def query(self, query_text, n_results, where=None):
            selected = self.docs[:n_results]
            return {
                "ids": [[item["id"] for item in selected]],
                "documents": [[item["content"] for item in selected]],
                "distances": [[item["distance"] for item in selected]],
                "metadatas": [[{"namespace": "test"} for _ in selected]],
            }

    class FakeDB:
        def get_memories_by_ids(self, memory_ids):
            rows = {}
            for memory_id in memory_ids:
                status = "active" if memory_id.startswith("active") else "superseded"
                rows[memory_id] = {
                    "id": memory_id,
                    "namespace": "test",
                    "status": status,
                    "created_at": "2026-05-22T00:00:00+00:00",
                    "access_count": 0,
                    "memory_type": None,
                    "type_confidence": None,
                    "type_source": None,
                    "superseded_by": None,
                    "metadata_json": "{}",
                }
            return rows

        def search_fts(self, query, namespace=None, limit=5):
            return []

        def record_interaction(self, memory_id, interaction_type, agent_id):
            return None

    class FakeEmbedder:
        def count_tokens(self, content):
            return 1

    recall = RecallEngine(db=FakeDB(), chroma=FakeChroma(), embedder=FakeEmbedder())

    results = recall.recall("query", namespace="test", limit=2)

    assert [item["id"] for item in results] == ["active-1", "active-2"]
