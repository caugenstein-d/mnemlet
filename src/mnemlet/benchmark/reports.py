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

    live_results = result.get("live_results", [])
    if live_results:
        lines.extend(
            [
                "",
                "## Live Checks",
                "",
                "These checks are environment-dependent and reflect the local machine configuration at run time.",
                "",
                "| Name | Surface | Success | Details |",
                "| --- | --- | --- | --- |",
            ]
        )
        for item in live_results:
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
    if item.get("success") is False and item.get("returncode") is not None:
        return f"exit {item['returncode']}"
    missing = item.get("missing")
    if missing:
        return "missing: " + ", ".join(str(value) for value in missing)
    return ""


def _markdown_cell(value: Any) -> str:
    return str(value).replace("|", "\\|").replace("\n", " ")


def _write_csv(result: dict[str, Any], path: Path) -> None:
    if result.get("mode") == "quality":
        _write_quality_csv(result, path)
        return
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


def _write_quality_csv(result: dict[str, Any], path: Path) -> None:
    fields = ["scenario_id", "category", "passed", "assertion_type", "assertion_pass"]
    with path.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=fields)
        writer.writeheader()
        for scenario in result.get("scenarios", []):
            assertions = scenario.get("assertions", []) or [{"type": "scenario", "pass": scenario.get("passed", False)}]
            for assertion in assertions:
                writer.writerow(
                    {
                        "scenario_id": scenario.get("id", ""),
                        "category": scenario.get("category", ""),
                        "passed": scenario.get("passed", False),
                        "assertion_type": assertion.get("type", ""),
                        "assertion_pass": assertion.get("pass", False),
                    }
                )


def _weak_cases(result: dict[str, Any]) -> list[tuple[dict[str, Any], str]]:
    weak: list[tuple[dict[str, Any], str]] = []
    for query in result.get("queries", []):
        returned_ids = set(_returned_logical_ids(query))
        expected_ids = set(query.get("expected_memory_ids", []))
        expected_substrings = list(query.get("expected_substrings", []))
        expected_namespaces = set(query.get("expected_namespaces", []))
        forbidden_ids = set(query.get("forbidden_memory_ids", []))
        reasons: list[str] = []
        first_rank = _first_expected_rank(query)
        has_expectations = bool(expected_ids or expected_substrings or expected_namespaces)
        if query.get("no_hit") and returned_ids:
            reasons.append("false_positive")
        elif has_expectations and first_rank is None:
            reasons.append("missing_expected")
        if expected_substrings and not _has_expected_substring(query):
            reasons.append("missing_expected_substring")
        if expected_namespaces and not _has_expected_namespace(query):
            reasons.append("missing_expected_namespace")
        if forbidden_ids.intersection(returned_ids):
            reasons.append("forbidden_hit")
        min_expected_rank = int(query.get("min_expected_rank", 1))
        if first_rank is not None and first_rank > min_expected_rank:
            reasons.append("rank_gt_min")
        if reasons:
            weak.append((query, ", ".join(reasons)))
    return weak


def _returned_logical_ids(query: dict[str, Any]) -> list[str]:
    return [
        str(item["logical_id"])
        for item in query.get("results", [])
        if item.get("logical_id") is not None
    ]


def _has_expected_substring(query: dict[str, Any]) -> bool:
    expected_substrings = list(query.get("expected_substrings", []))
    return any(
        substring in str(item.get("content", ""))
        for item in query.get("results", [])
        for substring in expected_substrings
    )


def _has_expected_namespace(query: dict[str, Any]) -> bool:
    expected_namespaces = set(query.get("expected_namespaces", []))
    return any(item.get("namespace") in expected_namespaces for item in query.get("results", []))


def _first_expected_rank(query: dict[str, Any]) -> int | None:
    for index, item in enumerate(query.get("results", []), start=1):
        if _matches_expected(query, item):
            return index
    return None


def _matches_expected(query: dict[str, Any], item: dict[str, Any]) -> bool:
    expected_namespaces = set(query.get("expected_namespaces", []))
    if expected_namespaces and item.get("namespace") not in expected_namespaces:
        return False

    expected_ids = set(query.get("expected_memory_ids", query.get("expected", [])))
    if expected_ids and item.get("logical_id") in expected_ids:
        return True

    expected_substrings = list(query.get("expected_substrings", []))
    content = str(item.get("content", ""))
    if expected_substrings and any(substring in content for substring in expected_substrings):
        return True

    return bool(expected_namespaces and not expected_ids and not expected_substrings)
