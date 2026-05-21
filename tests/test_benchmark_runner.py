"""Tests for isolated benchmark runner."""

from pathlib import Path

from mnemlet.benchmark.datasets import load_dataset
from mnemlet.benchmark.runner import BenchmarkRunner, run_retrieval_benchmark


def test_runner_uses_isolated_storage(tmp_path: Path) -> None:
    dataset = load_dataset("public", root=Path.cwd())
    output_dir = tmp_path / "out"

    result = run_retrieval_benchmark(dataset, output_dir=output_dir, limit=3, min_score=0.0)

    assert result["dataset"] == "public-synthetic"
    assert result["query_count"] == 48
    assert result["storage"]["data_dir"].startswith(str(output_dir))
    assert len(result["queries"]) == 48


def test_runner_maps_logical_ids_to_real_memory_ids(tmp_path: Path) -> None:
    dataset = load_dataset("public", root=Path.cwd())
    runner = BenchmarkRunner(dataset=dataset, output_dir=tmp_path, limit=5, min_score=0.0)

    runner.setup()
    try:
        assert "memory_bridge_codename" in runner.memory_id_map
        real_id = runner.memory_id_map["memory_bridge_codename"]
        assert runner.reverse_memory_id_map[real_id] == "memory_bridge_codename"
    finally:
        runner.close()
