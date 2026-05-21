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


def test_runner_includes_canonical_query_result_aliases(tmp_path: Path) -> None:
    dataset = load_dataset("public", root=Path.cwd())

    result = run_retrieval_benchmark(dataset, output_dir=tmp_path, limit=3, min_score=0.0)
    query_result = result["queries"][0]

    assert "expected_memory_ids" in query_result
    assert "forbidden_memory_ids" in query_result
    assert "latency_ms" in query_result
    assert "expected" in query_result
    assert "forbidden" in query_result
    assert "latency" in query_result
    assert query_result["expected"] == query_result["expected_memory_ids"]
    assert query_result["forbidden"] == query_result["forbidden_memory_ids"]
    assert query_result["latency"] == query_result["latency_ms"]
