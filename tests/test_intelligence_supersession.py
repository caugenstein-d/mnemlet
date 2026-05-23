"""Tests for automatic supersession with an injected contradiction detector."""

import json
import tempfile
from pathlib import Path

import pytest

from mnemlet.engine.ingest import IngestEngine
from mnemlet.intelligence.supersession import ContradictionDecision, SupersessionEngine
from mnemlet.storage.chroma import MnemletChroma
from mnemlet.storage.embeddings import MnemletEmbedding
from mnemlet.storage.sqlite import MnemletDB


class FakeDetector:
    def __init__(self, contradiction: bool, confidence: float) -> None:
        self.contradiction = contradiction
        self.confidence = confidence

    def detect(self, new_content: str, existing_content: str) -> ContradictionDecision:
        return ContradictionDecision(self.contradiction, self.confidence, "fake")


@pytest.fixture(scope="module")
def embedder() -> MnemletEmbedding:
    return MnemletEmbedding()


def test_high_confidence_fact_contradiction_supersedes_old_memory(embedder: MnemletEmbedding) -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        db = MnemletDB(base / "test.db")
        chroma = MnemletChroma(base / "chroma", embedder)
        supersession = SupersessionEngine(db=db, detector=FakeDetector(True, 0.95))
        ingest = IngestEngine(db=db, chroma=chroma, embedder=embedder, supersession_engine=supersession)

        old = ingest.ingest("The service runs on port 8080", namespace="infra", memory_type="fact", type_source="manual")
        new = ingest.ingest("The service runs on port 9090", namespace="infra", memory_type="fact", type_source="manual")

        old_memory = db.get_memory(str(old["memory_id"]))
        new_memory = db.get_memory(str(new["memory_id"]))

    assert old_memory["status"] == "superseded"
    assert old_memory["superseded_by"] == new["memory_id"]
    assert '"supersedes": "' + str(old["memory_id"]) + '"' in new_memory["metadata_json"]


def test_instruction_contradiction_is_flagged_not_superseded(embedder: MnemletEmbedding) -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        db = MnemletDB(base / "test.db")
        chroma = MnemletChroma(base / "chroma", embedder)
        supersession = SupersessionEngine(db=db, detector=FakeDetector(True, 0.95))
        ingest = IngestEngine(db=db, chroma=chroma, embedder=embedder, supersession_engine=supersession)

        old = ingest.ingest("OpenWebUI darf nicht restarted werden", namespace="ops", memory_type="instruction", type_source="manual")
        new = ingest.ingest("OpenWebUI darf restarted werden", namespace="ops", memory_type="instruction", type_source="manual")

        old_memory = db.get_memory(str(old["memory_id"]))
        new_memory = db.get_memory(str(new["memory_id"]))

    assert old_memory["status"] == "active"
    assert new_memory["status"] == "active"
    assert "supersede_protected" in old_memory["metadata_json"]
    assert "contradiction_unresolved" in new_memory["metadata_json"]


def test_no_contradiction_leaves_memories_active(embedder: MnemletEmbedding) -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        db = MnemletDB(base / "test.db")
        chroma = MnemletChroma(base / "chroma", embedder)
        supersession = SupersessionEngine(db=db, detector=FakeDetector(False, 0.95))
        ingest = IngestEngine(db=db, chroma=chroma, embedder=embedder, supersession_engine=supersession)

        first = ingest.ingest("The service runs on port 8080", namespace="infra", memory_type="fact", type_source="manual")
        second = ingest.ingest("The service uses PostgreSQL", namespace="infra", memory_type="fact", type_source="manual")

        first_memory = db.get_memory(str(first["memory_id"]))
        second_memory = db.get_memory(str(second["memory_id"]))

    assert first_memory["status"] == "active"
    assert second_memory["status"] == "active"
    assert second["superseded_ids"] == []
    assert second["contradiction_detected"] is False


def test_low_confidence_contradiction_is_flagged_not_superseded(embedder: MnemletEmbedding) -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        db = MnemletDB(base / "test.db")
        chroma = MnemletChroma(base / "chroma", embedder)
        supersession = SupersessionEngine(db=db, detector=FakeDetector(True, 0.5))
        ingest = IngestEngine(db=db, chroma=chroma, embedder=embedder, supersession_engine=supersession)

        old = ingest.ingest("The service runs on port 8080", namespace="infra", memory_type="fact", type_source="manual")
        new = ingest.ingest("The service runs on port 9090", namespace="infra", memory_type="fact", type_source="manual")

        old_memory = db.get_memory(str(old["memory_id"]))
        new_memory = db.get_memory(str(new["memory_id"]))

    assert old_memory["status"] == "active"
    assert new_memory["status"] == "active"
    assert "supersede_protected" in old_memory["metadata_json"]
    assert "contradiction_unresolved" in new_memory["metadata_json"]


def test_explicit_supersede_metadata_blocks_auto_supersession(embedder: MnemletEmbedding) -> None:
    """When metadata already declares supersede_reason, SupersessionEngine must defer."""
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        db = MnemletDB(base / "test.db")
        chroma = MnemletChroma(base / "chroma", embedder)
        supersession = SupersessionEngine(db=db, detector=FakeDetector(True, 0.95))
        ingest = IngestEngine(db=db, chroma=chroma, embedder=embedder, supersession_engine=supersession)

        seed = ingest.ingest("Seed fact A", namespace="infra", memory_type="fact", type_source="manual")
        new = ingest.ingest(
            "Replace fact A explicitly",
            namespace="infra",
            memory_type="fact",
            type_source="manual",
            metadata={"supersedes": str(seed["memory_id"]), "supersede_reason": "replace"},
        )

        new_memory = db.get_memory(str(new["memory_id"]))
        seed_memory = db.get_memory(str(seed["memory_id"]))

    # Manual replace metadata is preserved
    new_metadata = json.loads(new_memory["metadata_json"])
    assert new_metadata["supersede_reason"] == "replace"
    # Auto-supersession did not run, so seed is still active (replace happens at REST/MCP layer, not via IngestEngine)
    assert seed_memory["status"] == "active"
    assert new["superseded_ids"] == []


def test_repeated_unresolved_contradictions_merge_metadata(embedder: MnemletEmbedding) -> None:
    """Multiple low-confidence contradictions accumulate flags + ids, not clobber."""
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        db = MnemletDB(base / "test.db")
        chroma = MnemletChroma(base / "chroma", embedder)
        supersession = SupersessionEngine(db=db, detector=FakeDetector(True, 0.5))
        ingest = IngestEngine(db=db, chroma=chroma, embedder=embedder, supersession_engine=supersession)

        first = ingest.ingest("The service runs on port 8080", namespace="infra", memory_type="fact", type_source="manual")
        second = ingest.ingest("The service runs on port 9090", namespace="infra", memory_type="fact", type_source="manual")
        third = ingest.ingest("The service runs on port 9091", namespace="infra", memory_type="fact", type_source="manual")

        first_meta = json.loads(db.get_memory(str(first["memory_id"]))["metadata_json"])

    contradicts = first_meta.get("contradicts_with") or []
    flags = first_meta.get("policy_flags") or []
    assert str(second["memory_id"]) in contradicts
    assert str(third["memory_id"]) in contradicts
    assert flags.count("supersede_protected") == 1
