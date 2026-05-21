"""Tests for benchmark report writers."""

from __future__ import annotations

import csv
import json
from pathlib import Path

from mnemlet.benchmark.reports import write_reports


def sample_result() -> dict:
    return {
        "run_id": "unit-run",
        "mode": "quick",
        "dataset": "public-synthetic",
        "command": "mnemlet benchmark quick --dataset public",
        "environment": {"python": "3.12", "platform": "test", "git_commit": "abc123"},
        "summary": {
            "hit_at_1": 1.0,
            "hit_at_3": 1.0,
            "mrr": 1.0,
            "p95_latency_ms": 12.0,
        },
        "queries": [
            {
                "case_id": "case-1",
                "category": "retrieval",
                "query_id": "query-1",
                "query": "What is the answer?",
                "latency_ms": 12.0,
                "expected_memory_ids": ["m1"],
                "results": [
                    {
                        "logical_id": "m1",
                        "score": 0.9,
                        "namespace": "test",
                        "content": "answer",
                    }
                ],
            }
        ],
    }


def test_write_reports_creates_json_markdown_and_csv(tmp_path: Path) -> None:
    paths = write_reports(sample_result(), tmp_path, formats=("json", "md", "csv"))

    assert paths == {
        "json": tmp_path / "results.json",
        "md": tmp_path / "report.md",
        "csv": tmp_path / "results.csv",
    }
    assert (tmp_path / "results.json").exists()
    assert (tmp_path / "report.md").exists()
    assert (tmp_path / "results.csv").exists()
    assert json.loads((tmp_path / "results.json").read_text(encoding="utf-8"))["run_id"] == "unit-run"
    assert "# Mnémlet Benchmark Report" in (tmp_path / "report.md").read_text(encoding="utf-8")

    csv_text = (tmp_path / "results.csv").read_text(encoding="utf-8")
    assert "query_id,case_id,category" in csv_text
    rows = list(csv.DictReader(csv_text.splitlines()))
    assert rows[0]["returned_logical_ids"] == "m1"


def test_markdown_describes_methodology_environment_and_limitations(tmp_path: Path) -> None:
    write_reports(sample_result(), tmp_path, formats=("md",))

    markdown = (tmp_path / "report.md").read_text(encoding="utf-8")

    assert "## Methodology" in markdown
    assert "synthetic commit-safe memories" in markdown
    assert "isolated temporary Mnémlet storage" in markdown
    assert "## Environment" in markdown
    assert "## Limitations" in markdown
    assert "latency is hardware-specific" in markdown
    assert "temp storage is discarded after the run" in markdown
    assert "inspectable" not in markdown.lower()
    assert "persistent" not in markdown.lower()


def test_markdown_flags_forbidden_memory_hits(tmp_path: Path) -> None:
    result = sample_result()
    result["queries"] = [
        {
            "case_id": "case-1",
            "category": "retrieval",
            "query_id": "query-forbidden",
            "query": "What is the answer?",
            "latency_ms": 12.0,
            "expected_memory_ids": ["m1"],
            "forbidden_memory_ids": ["m2"],
            "results": [
                {"logical_id": "m1", "score": 0.9, "namespace": "test", "content": "answer"},
                {"logical_id": "m2", "score": 0.8, "namespace": "test", "content": "wrong"},
            ],
        }
    ]

    write_reports(result, tmp_path, formats=("md",))

    markdown = (tmp_path / "report.md").read_text(encoding="utf-8")
    assert "query-forbidden" in markdown
    assert "forbidden_hit" in markdown


def test_markdown_flags_no_hit_false_positive(tmp_path: Path) -> None:
    result = sample_result()
    result["queries"] = [
        {
            "case_id": "case-1",
            "category": "retrieval",
            "query_id": "query-no-hit",
            "query": "No matching memory should exist",
            "latency_ms": 12.0,
            "expected_memory_ids": [],
            "forbidden_memory_ids": [],
            "no_hit": True,
            "results": [
                {"logical_id": "m1", "score": 0.9, "namespace": "test", "content": "answer"},
            ],
        }
    ]

    write_reports(result, tmp_path, formats=("md",))

    markdown = (tmp_path / "report.md").read_text(encoding="utf-8")
    assert "query-no-hit" in markdown
    assert "false_positive" in markdown
