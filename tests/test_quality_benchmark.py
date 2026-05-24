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


from mnemlet.benchmark.quality import run_quality_benchmark


def test_run_quality_benchmark_returns_release_metrics(tmp_path: Path) -> None:
    dataset = load_quality_dataset("public", root=Path.cwd())

    result = run_quality_benchmark(dataset, output_dir=tmp_path)

    assert result["mode"] == "quality"
    assert result["scenario_count"] == len(dataset.scenarios)
    assert "empty_correct_rate" in result["summary"]
    assert "replace_supersession_rate" in result["summary"]
    assert "provenance_completeness" in result["summary"]
    assert "openwebui_success_rate" in result["summary"]
    assert "opencode_success_rate" in result["summary"]
