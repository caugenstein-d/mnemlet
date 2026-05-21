"""Tests for benchmark CLI commands."""

from __future__ import annotations

import os
import subprocess
from pathlib import Path


PYTHON = Path("/home/christoph/mnemlet/.venv/bin/python")


def test_benchmark_quick_writes_requested_reports(tmp_path: Path) -> None:
    env = os.environ.copy()
    env["PYTHONPATH"] = "src"

    result = subprocess.run(
        [
            str(PYTHON),
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
