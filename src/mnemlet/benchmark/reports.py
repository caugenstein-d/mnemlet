"""Report writers for Mnémlet benchmark runs."""

from __future__ import annotations

import csv
import json
import platform
import subprocess
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any


def environment_info() -> dict[str, str]:
    """Return basic runtime details for a benchmark report."""
    return {
        "python": f"{sys.version_info.major}.{sys.version_info.minor}.{sys.version_info.micro}",
        "platform": platform.platform(),
        "machine": platform.machine(),
        "git_commit": _git_commit(),
    }


def new_run_id() -> str:
    """Return a UTC timestamp suitable for report run IDs."""
    return datetime.now(UTC).strftime("%Y-%m-%dT%H-%M-%SZ")


def write_reports(
    result: dict[str, Any],
    output_dir: Path,
    formats: tuple[str, ...] = ("json", "md", "csv"),
) -> dict[str, Path]:
    """Write benchmark reports in the requested formats and return their paths."""
    output_dir.mkdir(parents=True, exist_ok=True)
    paths: dict[str, Path] = {}
    for report_format in formats:
        if report_format == "json":
            path = output_dir / "results.json"
            path.write_text(
                json.dumps(result, indent=2, ensure_ascii=False) + "\n",
                encoding="utf-8",
            )
        elif report_format == "md":
            path = output_dir / "report.md"
            path.write_text(_markdown_report(result), encoding="utf-8")
        elif report_format == "csv":
            path = output_dir / "results.csv"
            _write_csv(result, path)
        else:
            raise ValueError(f"unsupported benchmark report format: {report_format}")
        paths[report_format] = path
    return paths


def _git_commit() -> str:
    try:
        completed = subprocess.run(
            ["git", "rev-parse", "--short", "HEAD"],
            capture_output=True,
            text=True,
            check=False,
        )
    except OSError:
        return "unknown"
    commit = completed.stdout.strip()
    return commit or "unknown"


def _markdown_report(result: dict[str, Any]) -> str:
    lines = [
        "# Mnémlet Benchmark Report",
        "",
        f"Run ID: {result.get('run_id', 'unknown')}",
        f"Mode: {result.get('mode', 'unknown')}",
        f"Dataset: {result.get('dataset', 'unknown')}",
        f"Command: `{result.get('command', '')}`",
        "",
        "## Summary",
        "",
        "| Metric | Value |",
        "| --- | --- |",
    ]
    for key, value in result.get("summary", {}).items():
        lines.append(f"| {key} | {value} |")

    adapter_results = result.get("adapter_results", [])
    if adapter_results:
        lines.extend(
            [
                "",
                "## Adapter Checks",
                "",
                "| Name | Surface | Success | Details |",
                "| --- | --- | --- | --- |",
            ]
        )
        for item in adapter_results:
            lines.append(
                f"| {_markdown_cell(item.get('name', ''))} | {_markdown_cell(item.get('surface', ''))} | "
                f"{str(item.get('success') is True).lower()} | {_markdown_cell(_adapter_details(item))} |"
            )

    lines.extend(
        [
            "",
            "## Environment",
            "",
            "| Key | Value |",
            "| --- | --- |",
        ]
    )
    for key, value in result.get("environment", {}).items():
        lines.append(f"| {key} | {value} |")

    lines.extend(
        [
            "",
            "## Methodology",
            "",
            "Public benchmarks use synthetic commit-safe memories and isolated temporary Mnémlet storage.",
            "Retrieval queries are run against the loaded dataset, and aggregate metrics are computed from returned logical IDs.",
            "",
            "## Failed or Weak Cases",
            "",
        ]
    )
    weak_cases = _weak_cases(result)
    if weak_cases:
        lines.extend(["| query_id | case_id | category | reason |", "| --- | --- | --- | --- |"])
        for query, reason in weak_cases:
            lines.append(
                f"| {query.get('query_id', '')} | {query.get('case_id', '')} | {query.get('category', '')} | {reason} |"
            )
    else:
        lines.append("No failed or weak cases detected.")

    lines.extend(
        [
            "",
            "## Limitations",
            "",
            "latency is hardware-specific and may vary across machines and concurrent workloads.",
            "temp storage is discarded after the run.",
            "",
        ]
    )
    return "\n".join(lines)


def _adapter_details(item: dict[str, Any]) -> str:
    if item.get("error"):
        return str(item["error"])
    missing = item.get("missing")
    if missing:
        return "missing: " + ", ".join(str(value) for value in missing)
    return ""


def _markdown_cell(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def _write_csv(result: dict[str, Any], path: Path) -> None:
    fields = [
        "query_id",
        "case_id",
        "category",
        "latency_ms",
        "expected_memory_ids",
        "returned_logical_ids",
    ]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for query in result.get("queries", []):
            writer.writerow(
                {
                    "query_id": query.get("query_id", ""),
                    "case_id": query.get("case_id", ""),
                    "category": query.get("category", ""),
                    "latency_ms": query.get("latency_ms", ""),
                    "expected_memory_ids": ";".join(query.get("expected_memory_ids", [])),
                    "returned_logical_ids": ";".join(_returned_logical_ids(query)),
                }
            )


def _weak_cases(result: dict[str, Any]) -> list[tuple[dict[str, Any], str]]:
    weak: list[tuple[dict[str, Any], str]] = []
    for query in result.get("queries", []):
        returned_ids = set(_returned_logical_ids(query))
        expected_ids = set(query.get("expected_memory_ids", []))
        forbidden_ids = set(query.get("forbidden_memory_ids", []))
        reasons: list[str] = []
        if query.get("no_hit") and returned_ids:
            reasons.append("false_positive")
        elif expected_ids and not expected_ids.intersection(returned_ids):
            reasons.append("missing_expected")
        if forbidden_ids.intersection(returned_ids):
            reasons.append("forbidden_hit")
        if reasons:
            weak.append((query, ", ".join(reasons)))
    return weak


def _returned_logical_ids(query: dict[str, Any]) -> list[str]:
    return [
        str(item["logical_id"])
        for item in query.get("results", [])
        if item.get("logical_id") is not None
    ]
