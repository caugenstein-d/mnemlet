"""Tests for Memory Intelligence review commands."""

import tempfile
from pathlib import Path

import pytest

from mnemlet.engine.ingest import IngestEngine
from mnemlet.intelligence.review import ReviewService
from mnemlet.storage.chroma import MnemletChroma
from mnemlet.storage.embeddings import MnemletEmbedding
from mnemlet.storage.sqlite import MnemletDB


@pytest.fixture(scope="module")
def embedder() -> MnemletEmbedding:
    return MnemletEmbedding()


@pytest.fixture
def review(embedder: MnemletEmbedding) -> ReviewService:
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        db = MnemletDB(base / "test.db")
        chroma = MnemletChroma(base / "chroma", embedder)
        ingest = IngestEngine(db=db, chroma=chroma, embedder=embedder)
        yield ReviewService(db=db, ingest_engine=ingest)
        db.close()


def test_remember_stores_explicit_memory_type(review: ReviewService) -> None:
    result = review.remember("OpenWebUI darf nicht restarted werden", "ops", 0.9, "instruction")

    assert result["stored"] is True
    memory = review.db.get_memory(str(result["memory_id"]))
    assert memory["memory_type"] == "instruction"
    assert memory["type_source"] == "manual"


def test_forget_marks_memory_without_deleting(review: ReviewService) -> None:
    result = review.remember("Temporary detail", "notes", 0.3)

    forgotten = review.forget(str(result["memory_id"]))

    assert forgotten["status"] == "forgotten"
    assert review.db.get_memory(str(result["memory_id"])) is not None


def test_replace_supersedes_old_memory_and_links_new(review: ReviewService) -> None:
    old = review.remember("The service runs on port 8080", "infra", 0.5, "fact")

    replaced = review.replace(str(old["memory_id"]), "The service runs on port 9090", 0.8)

    old_memory = review.db.get_memory(str(old["memory_id"]))
    new_memory = review.db.get_memory(str(replaced["new_id"]))
    assert old_memory["status"] == "superseded"
    assert old_memory["superseded_by"] == replaced["new_id"]
    assert '"supersedes": "' + str(old["memory_id"]) + '"' in new_memory["metadata_json"]


def test_confirm_boosts_retention_and_records_interaction(review: ReviewService) -> None:
    result = review.remember("Important preference", "prefs", 0.4)
    before = review.db.get_memory(str(result["memory_id"]))["retention_score"]

    confirmed = review.confirm(str(result["memory_id"]))
    interactions = review.db.get_interactions(str(result["memory_id"]))

    assert confirmed["retention_score"] > before
    assert any(item["interaction_type"] == "confirm" for item in interactions)


def test_remember_bypasses_duplicate_suppression(review: ReviewService) -> None:
    first = review.remember("Identical content here", "x", 0.5)
    second = review.remember("Identical content here", "x", 0.5)

    assert first["stored"] is True
    assert second["stored"] is True
    assert first["memory_id"] != second["memory_id"]
    assert review.db.get_memory(str(first["memory_id"])) is not None
    assert review.db.get_memory(str(second["memory_id"])) is not None


def test_remember_rejects_invalid_memory_type(review: ReviewService) -> None:
    with pytest.raises(ValueError):
        review.remember("content", "x", 0.5, "garbage")

    count = review.db.conn.execute(
        "SELECT COUNT(*) FROM memories WHERE namespace = 'x'"
    ).fetchone()[0]
    assert count == 0
