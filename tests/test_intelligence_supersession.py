"""Tests for automatic supersession with an injected contradiction detector."""

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
