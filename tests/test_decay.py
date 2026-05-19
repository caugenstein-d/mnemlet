"""Tests for the decay engine."""

import math
import tempfile
from pathlib import Path
from datetime import datetime, timezone, timedelta
import pytest
from mnemlet.storage.sqlite import MnemletDB
from mnemlet.engine.decay import DecayEngine
from mnemlet.constants import (
    BOOST_RECALL, BOOST_UPDATE, BOOST_CREATE, BOOST_REFERENCE, PENALTY_IGNORE,
    DEFAULT_LAMBDA, DEFAULT_PURGE_THRESHOLD,
)


@pytest.fixture
def engine():
    with tempfile.TemporaryDirectory() as tmpdir:
        db = MnemletDB(Path(tmpdir) / "test.db")
        eng = DecayEngine(db)
        yield eng


def test_calculate_decay_no_time_passed(engine):
    """If no time has passed, score stays the same."""
    score = engine.calculate_decay(0.8, days_elapsed=0.0, lambda_=0.01)
    assert score == pytest.approx(0.8)


def test_calculate_decay_after_days(engine):
    """After some days, score decays exponentially."""
    score = engine.calculate_decay(0.8, days_elapsed=30.0, lambda_=0.01)
    # score = 0.8 * e^(-0.01 * 30) = 0.8 * e^(-0.3) ≈ 0.8 * 0.7408 ≈ 0.593
    expected = 0.8 * math.exp(-0.01 * 30)
    assert score == pytest.approx(expected, rel=1e-4)


def test_calculate_decay_faster_lambda(engine):
    """Higher lambda causes faster decay."""
    score = engine.calculate_decay(0.8, days_elapsed=10.0, lambda_=0.05)
    # score = 0.8 * e^(-0.05 * 10) = 0.8 * e^(-0.5) ≈ 0.8 * 0.6065 ≈ 0.485
    expected = 0.8 * math.exp(-0.5)
    assert score == pytest.approx(expected, rel=1e-4)


def test_apply_boost_recall(engine):
    """A recall interaction boosts the score (capped at 1.0)."""
    new_score = engine.apply_boost(0.3, "recall")
    assert new_score == pytest.approx(0.45)  # 0.3 + 0.15


def test_apply_boost_update(engine):
    """An update gives the highest boost."""
    new_score = engine.apply_boost(0.3, "update")
    assert new_score == pytest.approx(0.50)  # 0.3 + 0.20


def test_apply_boost_capped_at_one(engine):
    """Score never exceeds 1.0."""
    new_score = engine.apply_boost(0.95, "update")
    assert new_score == 1.0


def test_apply_boost_create(engine):
    """A create interaction gives initial boost."""
    new_score = engine.apply_boost(0.0, "create")
    assert new_score == pytest.approx(0.10)


def test_apply_penalty_ignore(engine):
    """An ignored memory gets a small penalty."""
    new_score = engine.apply_boost(0.5, "ignore")
    assert new_score == pytest.approx(0.48)  # 0.5 - 0.02


def test_apply_boost_unknown_type(engine):
    """Unknown interaction type raises ValueError."""
    with pytest.raises(ValueError):
        engine.apply_boost(0.5, "fantasy_interaction")


def test_boost_applied_in_db(engine):
    """Boost is applied to actual DB record with interaction tracking."""
    engine.db.insert_memory(memory_id="test-b", namespace="test", content_preview="test")
    engine.db.update_score("test-b", 0.4)

    result = engine.boost_memory("test-b", "recall", agent_id="claude-code")
    assert result["retention_score"] == pytest.approx(0.55)  # 0.4 + 0.15

    # Verify interaction was recorded
    interactions = engine.db.get_interactions("test-b", limit=5)
    assert len(interactions) >= 1
    assert interactions[0]["interaction_type"] == "recall"


def test_purge_cold_storage(engine):
    """Memories below purge threshold are moved to cold storage."""
    engine.db.insert_memory(memory_id="cold-1", namespace="test", content_preview="fading")
    engine.db.update_score("cold-1", 0.03)  # Below 0.05 threshold

    result = engine.run_purge(purge_threshold=0.05, dry_run=False)
    assert result["moved_to_cold"] >= 1
    assert result["hard_deleted"] == 0

    memory = engine.db.get_memory("cold-1")
    assert memory["status"] == "cold_storage"


def test_purge_hard_delete(engine):
    """Very old, very low-score memories are hard-deleted."""
    engine.db.insert_memory(memory_id="dead-1", namespace="test", content_preview="ancient")
    engine.db.update_score("dead-1", 0.005)  # Below 0.01

    # Simulate old age by directly updating created_at
    engine.db.conn.execute(
        "UPDATE memories SET created_at = '2025-01-01T00:00:00' WHERE id = 'dead-1'"
    )
    engine.db.conn.commit()

    result = engine.run_purge(purge_threshold=0.05, hard_delete_threshold=0.01,
                              hard_delete_age_days=90, dry_run=False)
    assert result["hard_deleted"] >= 1

    memory = engine.db.get_memory("dead-1")
    assert memory is None or memory["status"] == "deleted"


def test_purge_dry_run(engine):
    """Dry run doesn't actually change anything."""
    engine.db.insert_memory(memory_id="dry-1", namespace="test", content_preview="dry run test")
    engine.db.update_score("dry-1", 0.03)

    result = engine.run_purge(purge_threshold=0.05, dry_run=True)
    assert result["moved_to_cold"] >= 1

    memory = engine.db.get_memory("dry-1")
    assert memory["status"] == "active"  # Unchanged in dry run


def test_purge_respects_threshold(engine):
    """Memories above threshold are not purged."""
    engine.db.insert_memory(memory_id="keep-1", namespace="test", content_preview="important")
    engine.db.update_score("keep-1", 0.5)  # Well above threshold

    result = engine.run_purge(purge_threshold=0.05, dry_run=False)
    assert result["moved_to_cold"] == 0

    memory = engine.db.get_memory("keep-1")
    assert memory["status"] == "active"
