"""Tests for the Memory Intelligence Quality Benchmark."""

from pathlib import Path
from typing import Any

import pytest

from mnemlet.benchmark.datasets import QualityDataset, QualityPhase, QualityScenario, load_quality_dataset
from mnemlet.benchmark.quality import QualityRunner, run_quality_benchmark


def _quality_dataset(scenarios: list[QualityScenario] | None = None) -> QualityDataset:
    return QualityDataset(name="unit-quality", version=1, scenarios=scenarios or [])


def _quality_scenario(scenario_id: str, phases: list[QualityPhase]) -> QualityScenario:
    return QualityScenario(
        id=scenario_id,
        category="unit",
        description=f"Unit scenario {scenario_id}",
        phases=phases,
    )


def _phase(step: int, action: str, payload: dict[str, Any]) -> QualityPhase:
    return QualityPhase(step=step, action=action, payload=payload)


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


def test_quality_summary_false_positive_rate_is_zero_without_abstention_assertions(tmp_path: Path) -> None:
    runner = QualityRunner(_quality_dataset(), output_dir=tmp_path)

    summary = runner._summary(
        [
            {
                "id": "contains-only",
                "category": "unit",
                "passed": True,
                "assertions": [{"type": "contains", "pass": True}],
            }
        ]
    )

    assert summary["false_positive_rate"] == 0.0


def test_quality_runner_reports_missing_memory_for_status_assertion(tmp_path: Path) -> None:
    runner = QualityRunner(_quality_dataset(), output_dir=tmp_path)
    runner.setup()
    try:
        runner.logical_ids["ghost"] = "missing-real-id"

        assertions = runner._run_phase("assert_status", {"memory_id": "ghost", "status": "forgotten"})
    finally:
        runner.close()

    assert assertions == [
        {
            "type": "missing_memory",
            "assertion": "assert_status",
            "pass": False,
            "memory_id": "ghost",
            "real_id": "missing-real-id",
        }
    ]


def test_quality_runner_reports_missing_memory_for_confirm(tmp_path: Path) -> None:
    runner = QualityRunner(_quality_dataset(), output_dir=tmp_path)
    runner.setup()
    try:
        runner.logical_ids["ghost"] = "missing-real-id"

        assertions = runner._run_phase("confirm", {"memory_id": "ghost"})
    finally:
        runner.close()

    assert assertions == [
        {
            "type": "missing_memory",
            "assertion": "confirm",
            "pass": False,
            "memory_id": "ghost",
            "real_id": "missing-real-id",
        }
    ]
