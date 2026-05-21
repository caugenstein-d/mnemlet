"""Tests for benchmark CLI commands."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


def test_benchmark_quick_writes_requested_reports(tmp_path: Path) -> None:
    env = os.environ.copy()
    env["PYTHONPATH"] = "src"

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "mnemlet",
            "benchmark",
            "quick",
            "--dataset",
            "public",
            "--output",
            str(tmp_path),
            "--format",
            "json,md,csv",
            "--retrieval-only",
        ],
        cwd=Path.cwd(),
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )

    assert result.returncode == 0, result.stderr
    assert (tmp_path / "results.json").exists()
    assert (tmp_path / "report.md").exists()
    assert (tmp_path / "results.csv").exists()
    assert "Benchmark complete" in result.stdout


def test_benchmark_quick_rejects_invalid_format_before_running(tmp_path: Path) -> None:
    env = os.environ.copy()
    env["PYTHONPATH"] = "src"

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "mnemlet",
            "benchmark",
            "quick",
            "--dataset",
            "public",
            "--output",
            str(tmp_path),
            "--format",
            "xml",
            "--retrieval-only",
        ],
        cwd=Path.cwd(),
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )

    assert result.returncode != 0
    assert "unsupported" in result.stderr.lower() or "invalid" in result.stderr.lower()
    assert "Traceback" not in result.stderr
    assert not (tmp_path / "results.json").exists()


def test_benchmark_quick_include_adapters_writes_adapter_details(tmp_path: Path) -> None:
    env = os.environ.copy()
    env["PYTHONPATH"] = "src"

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "mnemlet",
            "benchmark",
            "quick",
            "--dataset",
            "public",
            "--output",
            str(tmp_path),
            "--format",
            "json,md",
            "--include-adapters",
        ],
        cwd=Path.cwd(),
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )

    assert result.returncode == 0, result.stderr
    report = json.loads((tmp_path / "results.json").read_text(encoding="utf-8"))
    markdown = (tmp_path / "report.md").read_text(encoding="utf-8")
    assert report["adapter_results"]
    assert "## Adapter Checks" in markdown
    assert "rest_recall" in markdown
