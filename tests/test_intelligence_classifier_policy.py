"""Tests for deterministic memory classification and MVP lifecycle policies."""

from mnemlet.intelligence.classifier import classify_memory
from mnemlet.intelligence.policy import can_auto_supersede, recall_statuses


def test_classifier_detects_preferences() -> None:
    result = classify_memory("Christoph bevorzugt Self-Hosting für AI tools", "prefs")

    assert result.memory_type == "preference"
    assert result.source == "heuristic"
    assert 0.7 <= result.confidence <= 0.8


def test_classifier_detects_instructions_before_preferences() -> None:
    result = classify_memory("OpenWebUI darf nicht restarted werden", "ops")

    assert result.memory_type == "instruction"
    assert result.summary == "OpenWebUI darf nicht restarted werden"


def test_classifier_defaults_to_context() -> None:
    result = classify_memory("Repo liegt unter /home/christoph/mnemlet", "project")

    assert result.memory_type == "context"
    assert result.confidence == 0.5


def test_policy_allows_safe_supersession_types() -> None:
    assert can_auto_supersede("fact") is True
    assert can_auto_supersede("preference") is True
    assert can_auto_supersede("context") is True


def test_policy_protects_instructions_events_and_unknown_types() -> None:
    assert can_auto_supersede("instruction") is False
    assert can_auto_supersede("event") is False
    assert can_auto_supersede(None) is False


def test_recall_statuses_default_to_active_only() -> None:
    assert recall_statuses(include_superseded=False) == {"active"}
    assert recall_statuses(include_superseded=True) == {"active", "superseded"}
