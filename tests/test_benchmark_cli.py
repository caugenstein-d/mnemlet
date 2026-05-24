"""Tests for benchmark CLI commands."""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


def _run_benchmark_cli(args: list[str], output_dir: Path) -> subprocess.CompletedProcess[str]:
    env = os.environ.copy()
    env["PYTHONPATH"] = "src"
    return subprocess.run(
        [sys.executable, "-m", "mnemlet", "benchmark", *args, "--output", str(output_dir), "--format", "json"],
        cwd=Path.cwd(),
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )


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


def test_benchmark_full_retrieval_only_skips_live_checks_even_when_requested(tmp_path: Path) -> None:
    fake_bin = tmp_path / "bin"
    fake_bin.mkdir()
    marker = tmp_path / "opencode-called.txt"
    fake_opencode = fake_bin / "opencode"
    fake_opencode.write_text(
        f"#!/usr/bin/env python3\nfrom pathlib import Path\nPath({str(marker)!r}).write_text('called', encoding='utf-8')\nraise SystemExit(7)\n",
        encoding="utf-8",
    )
    fake_opencode.chmod(0o755)

    env = os.environ.copy()
    env["PYTHONPATH"] = "src"
    env["PATH"] = f"{fake_bin}{os.pathsep}{env['PATH']}"

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "mnemlet",
            "benchmark",
            "full",
            "--dataset",
            "public",
            "--output",
            str(tmp_path),
            "--format",
            "json",
            "--retrieval-only",
            "--include-live-opencode",
        ],
        cwd=Path.cwd(),
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )

    assert result.returncode == 0, result.stderr
    report = json.loads((tmp_path / "results.json").read_text(encoding="utf-8"))
    assert report["live_results"] == []
    assert not marker.exists()


def test_benchmark_quality_writes_reports(tmp_path: Path) -> None:
    env = os.environ.copy()
    env["PYTHONPATH"] = "src"

    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "mnemlet",
            "benchmark",
            "quality",
            "--dataset",
            "public",
            "--output",
            str(tmp_path),
            "--format",
            "json,md,csv",
        ],
        cwd=Path.cwd(),
        env=env,
        capture_output=True,
        text=True,
        timeout=120,
    )

    assert result.returncode == 0, result.stderr
    assert (tmp_path / "results.json").exists()
    assert (tmp_path / "results.csv").exists()
    report = json.loads((tmp_path / "results.json").read_text(encoding="utf-8"))
    csv_text = (tmp_path / "results.csv").read_text(encoding="utf-8")
    assert report["mode"] == "quality"
    assert "empty_correct_rate" in report["summary"]
    assert "scenario_id,category,passed" in csv_text


def test_benchmark_quality_rejects_retrieval_only(tmp_path: Path) -> None:
    result = _run_benchmark_cli(["quality", "--dataset", "public", "--retrieval-only"], tmp_path)

    assert result.returncode != 0
    assert "unrecognized arguments" in result.stderr
    assert "--retrieval-only" in result.stderr
    assert not (tmp_path / "results.json").exists()


def test_benchmark_quality_rejects_limit_and_min_score(tmp_path: Path) -> None:
    result = _run_benchmark_cli(["quality", "--dataset", "public", "--limit", "2", "--min-score", "0.2"], tmp_path)

    assert result.returncode != 0
    assert "unrecognized arguments" in result.stderr
    assert "--limit" in result.stderr
    assert "--min-score" in result.stderr
    assert not (tmp_path / "results.json").exists()


def test_benchmark_quality_rejects_include_adapters(tmp_path: Path) -> None:
    result = _run_benchmark_cli(["quality", "--dataset", "public", "--include-adapters"], tmp_path)

    assert result.returncode != 0
    assert "unrecognized arguments" in result.stderr
    assert "--include-adapters" in result.stderr
    assert not (tmp_path / "results.json").exists()


def test_benchmark_quality_rejects_live_flags(tmp_path: Path) -> None:
    result = _run_benchmark_cli(["quality", "--dataset", "public", "--include-live-openwebui"], tmp_path)

    assert result.returncode != 0
    assert "unrecognized arguments" in result.stderr
    assert "--include-live-openwebui" in result.stderr
    assert not (tmp_path / "results.json").exists()
