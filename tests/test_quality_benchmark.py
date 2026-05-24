"""Tests for the Memory Intelligence Quality Benchmark."""

from pathlib import Path

from mnemlet.benchmark.datasets import load_quality_dataset


def test_load_public_quality_dataset() -> None:
    dataset = load_quality_dataset("public", root=Path.cwd())

    assert dataset.name == "quality-synthetic"
    assert dataset.version == 1
    assert len(dataset.scenarios) >= 12
    assert {scenario.category for scenario in dataset.scenarios} >= {
        "uncertainty_gating",
        "contradiction_handling",
        "fact_evolution",
        "agent_context_assembly",
        "provenance_tracking",
        "openwebui_integration_quality",
        "opencode_integration_quality",
    }
