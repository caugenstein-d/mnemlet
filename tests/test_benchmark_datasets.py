import json
from pathlib import Path

import pytest

from mnemlet.benchmark.datasets import (
    BenchmarkDatasetError,
    load_dataset,
    load_dataset_file,
    resolve_dataset_path,
)


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def valid_payload() -> dict:
    return {
        "name": "unit",
        "cases": [
            {
                "id": "case_one",
                "category": "exact_fact",
                "namespace": "prefs",
                "memories": [
                    {
                        "id": "memory_dark",
                        "content": "User prefers dark mode.",
                        "importance": 0.9,
                    },
                    {
                        "id": "memory_light",
                        "content": "The office has bright lights.",
                        "importance": 0.3,
                    },
                ],
                "queries": [
                    {
                        "id": "query_dark",
                        "query": "What editor theme does the user prefer?",
                        "expected_memory_ids": ["memory_dark"],
                        "forbidden_memory_ids": ["memory_light"],
                        "min_expected_rank": 1,
                    }
                ],
            }
        ],
    }


def test_valid_payload_loads_dataset(tmp_path: Path) -> None:
    path = tmp_path / "dataset.json"
    write_json(path, valid_payload())

    dataset = load_dataset_file(path)

    assert dataset.name == "unit"
    assert dataset.cases[0].id == "case_one"
    assert dataset.cases[0].queries[0].expected_memory_ids == ["memory_dark"]


def test_invalid_dataset_root_list_raises_error(tmp_path: Path) -> None:
    path = tmp_path / "dataset.json"
    path.write_text(json.dumps([]), encoding="utf-8")

    with pytest.raises(BenchmarkDatasetError, match="dataset root"):
        load_dataset_file(path)


@pytest.mark.parametrize("name", [None, ""])
def test_missing_or_blank_name_raises_error(tmp_path: Path, name: str | None) -> None:
    payload = valid_payload()
    if name is None:
        del payload["name"]
    else:
        payload["name"] = name
    path = tmp_path / "dataset.json"
    write_json(path, payload)

    with pytest.raises(BenchmarkDatasetError, match="name"):
        load_dataset_file(path)


@pytest.mark.parametrize("cases", [None, []])
def test_missing_or_empty_cases_raises_error(tmp_path: Path, cases: list | None) -> None:
    payload = valid_payload()
    if cases is None:
        del payload["cases"]
    else:
        payload["cases"] = cases
    path = tmp_path / "dataset.json"
    write_json(path, payload)

    with pytest.raises(BenchmarkDatasetError, match="cases"):
        load_dataset_file(path)


@pytest.mark.parametrize("field", ["id", "category", "namespace"])
def test_missing_case_required_field_raises_error(
    tmp_path: Path, field: str
) -> None:
    payload = valid_payload()
    del payload["cases"][0][field]
    path = tmp_path / "dataset.json"
    write_json(path, payload)

    with pytest.raises(BenchmarkDatasetError, match=field):
        load_dataset_file(path)


def test_missing_memory_content_raises_error(tmp_path: Path) -> None:
    payload = valid_payload()
    del payload["cases"][0]["memories"][0]["content"]
    path = tmp_path / "dataset.json"
    write_json(path, payload)

    with pytest.raises(BenchmarkDatasetError, match="content"):
        load_dataset_file(path)


def test_memory_importance_outside_range_raises_error(tmp_path: Path) -> None:
    payload = valid_payload()
    payload["cases"][0]["memories"][0]["importance"] = 1.1
    path = tmp_path / "dataset.json"
    write_json(path, payload)

    with pytest.raises(BenchmarkDatasetError, match="importance"):
        load_dataset_file(path)


def test_memory_tags_must_be_list_of_strings(tmp_path: Path) -> None:
    payload = valid_payload()
    payload["cases"][0]["memories"][0]["tags"] = ["ui", 7]
    path = tmp_path / "dataset.json"
    write_json(path, payload)

    with pytest.raises(BenchmarkDatasetError, match="tags"):
        load_dataset_file(path)


def test_memory_invalid_status_raises_error(tmp_path: Path) -> None:
    payload = valid_payload()
    payload["cases"][0]["memories"][0]["status"] = "archived"
    path = tmp_path / "dataset.json"
    write_json(path, payload)

    with pytest.raises(BenchmarkDatasetError, match="status"):
        load_dataset_file(path)


def test_duplicate_memory_id_raises_error(tmp_path: Path) -> None:
    payload = valid_payload()
    payload["cases"][0]["memories"][1]["id"] = "memory_dark"
    path = tmp_path / "dataset.json"
    write_json(path, payload)

    with pytest.raises(BenchmarkDatasetError, match="duplicate memory id"):
        load_dataset_file(path)


def test_duplicate_query_id_raises_error(tmp_path: Path) -> None:
    payload = valid_payload()
    payload["cases"][0]["queries"].append(payload["cases"][0]["queries"][0].copy())
    path = tmp_path / "dataset.json"
    write_json(path, payload)

    with pytest.raises(BenchmarkDatasetError, match="duplicate query id"):
        load_dataset_file(path)


def test_unknown_expected_id_raises_error(tmp_path: Path) -> None:
    payload = valid_payload()
    payload["cases"][0]["queries"][0]["expected_memory_ids"] = ["missing"]
    path = tmp_path / "dataset.json"
    write_json(path, payload)

    with pytest.raises(BenchmarkDatasetError, match="unknown expected memory id"):
        load_dataset_file(path)


def test_unknown_forbidden_id_raises_error(tmp_path: Path) -> None:
    payload = valid_payload()
    payload["cases"][0]["queries"][0]["forbidden_memory_ids"] = ["missing"]
    path = tmp_path / "dataset.json"
    write_json(path, payload)

    with pytest.raises(BenchmarkDatasetError, match="unknown forbidden memory id"):
        load_dataset_file(path)


def test_empty_expected_ids_without_no_hit_marker_raises_error(tmp_path: Path) -> None:
    payload = valid_payload()
    payload["cases"][0]["queries"][0]["expected_memory_ids"] = []
    path = tmp_path / "dataset.json"
    write_json(path, payload)

    with pytest.raises(BenchmarkDatasetError, match="no_hit"):
        load_dataset_file(path)


def test_no_hit_true_with_expected_ids_raises_error(tmp_path: Path) -> None:
    payload = valid_payload()
    payload["cases"][0]["queries"][0]["no_hit"] = True
    path = tmp_path / "dataset.json"
    write_json(path, payload)

    with pytest.raises(BenchmarkDatasetError, match="no_hit"):
        load_dataset_file(path)


def test_no_hit_category_without_explicit_marker_raises_error(tmp_path: Path) -> None:
    payload = valid_payload()
    payload["cases"][0]["category"] = "no_hit"
    payload["cases"][0]["queries"][0]["expected_memory_ids"] = []
    path = tmp_path / "dataset.json"
    write_json(path, payload)

    with pytest.raises(BenchmarkDatasetError, match="no_hit"):
        load_dataset_file(path)


def test_resolve_dataset_path_aliases(tmp_path: Path) -> None:
    assert resolve_dataset_path("public", root=tmp_path) == (
        tmp_path / "benchmarks/public/synthetic_memory_cases.json"
    )
    assert resolve_dataset_path("private", root=tmp_path) == (
        tmp_path / "benchmarks/private/real_world_cases.json"
    )


def test_public_fixture_loads_expected_query_count() -> None:
    dataset = load_dataset("public", root=Path.cwd())

    assert dataset.name == "public-synthetic"
    assert len(dataset.cases) == 8
    assert dataset.query_count == 48
