"""Tests for the decay engine."""

import math
import tempfile
from pathlib import Path
from datetime import datetime, timezone, timedelta
import pytest
from memoria.storage.sqlite import MemoriaDB
from memoria.engine.decay import DecayEngine
from memoria.constants import (
    BOOST_RECALL, BOOST_UPDATE, BOOST_CREATE, BOOST_REFERENCE, PENALTY_IGNORE,
    DEFAULT_LAMBDA, DEFAULT_PURGE_THRESHOLD,
)


@pytest.fixture
def engine():
    with tempfile.TemporaryDirectory() as tmpdir:
        db = MemoriaDB(Path(tmpdir) / "test.db")
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
