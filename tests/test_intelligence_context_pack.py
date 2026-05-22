"""Tests for Context Pack building and Abstention decisions."""

from mnemlet.intelligence.context_pack import build_context_pack


def test_context_pack_groups_primary_supporting_and_superseded() -> None:
    results = [
        {"id": "a", "content": "primary", "score": 0.8, "status": "active", "source": "vector", "rank": 1, "namespace": "n", "created_at": "now"},
        {"id": "b", "content": "supporting", "score": 0.4, "status": "active", "source": "fts", "rank": 2, "namespace": "n", "created_at": "now"},
        {"id": "c", "content": "weak", "score": 0.2, "status": "active", "source": "fts", "rank": 3, "namespace": "n", "created_at": "now"},
        {"id": "d", "content": "old", "score": 0.9, "status": "superseded", "source": "hybrid", "rank": 4, "namespace": "n", "created_at": "now"},
    ]

    pack = build_context_pack("query", results, include_superseded=True)

    assert [item["id"] for item in pack["context_pack"]["primary"]] == ["a"]
    assert [item["id"] for item in pack["context_pack"]["supporting"]] == ["b"]
    assert [item["id"] for item in pack["context_pack"]["superseded"]] == ["d"]
    assert pack["abstention"] is None
    assert pack["meta"]["pack_size"] == 3


def test_context_pack_abstains_on_no_results() -> None:
    pack = build_context_pack("unknown", [])

    assert pack["context_pack"] == {"primary": [], "supporting": [], "superseded": []}
    assert pack["abstention"]["reason"] == "no_relevant_memories"
    assert pack["meta"]["confidence"] == 0.0


def test_context_pack_abstains_on_low_confidence() -> None:
    results = [
        {"id": "weak", "content": "weak", "score": 0.2, "status": "active", "source": "vector", "rank": 1, "namespace": "n", "created_at": "now"}
    ]

    pack = build_context_pack("unknown", results)

    assert pack["context_pack"]["primary"] == []
    assert pack["context_pack"]["supporting"] == []
    assert pack["abstention"]["reason"] == "low_confidence_matches"


def test_context_pack_flags_contradictory_results() -> None:
    results = [
        {
            "id": "a",
            "content": "active contradiction",
            "score": 0.8,
            "status": "active",
            "source": "vector",
            "rank": 1,
            "namespace": "n",
            "created_at": "now",
            "policy_flags": ["contradiction_unresolved"],
        }
    ]

    pack = build_context_pack("query", results)

    assert pack["abstention"]["reason"] == "contradictory_results"
    assert "contradiction_unresolved" in pack["meta"]["policy_flags"]
