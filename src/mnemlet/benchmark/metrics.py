"""Retrieval metric calculations for benchmark runs."""

from __future__ import annotations

from collections.abc import Iterable
from math import ceil
from statistics import median
from typing import Any


def summarize_retrieval(
    query_results: list[dict[str, Any]], ks: Iterable[int] = (1, 3, 5)
) -> dict[str, float | int]:
    """Summarize retrieval quality and latency across benchmark query results."""
    k_values = tuple(ks)
    regular_cases = [result for result in query_results if not result.get("no_hit", False)]
    no_hit_cases = [result for result in query_results if result.get("no_hit", False)]
    forbidden_cases = [result for result in query_results if result.get("forbidden_memory_ids")]

    summary: dict[str, float | int] = {"query_count": len(query_results)}
    for k in k_values:
        summary[f"hit_at_{k}"] = _average(
            _hit_at(result, k) for result in regular_cases
        )
        summary[f"precision_at_{k}"] = _average(
            _precision_at(result, k) for result in regular_cases
        )

    summary["mrr"] = _average(_reciprocal_rank(result) for result in regular_cases)
    summary["false_positive_rate"] = _average(
        1.0 if result.get("results") else 0.0 for result in no_hit_cases
    )
    summary["forbidden_hit_rate"] = _average(
        _forbidden_hit(result) for result in forbidden_cases
    )

    latencies = sorted(float(result.get("latency_ms", 0.0)) for result in query_results)
    summary["p50_latency_ms"] = float(median(latencies)) if latencies else 0.0
    summary["p95_latency_ms"] = _nearest_rank_percentile(latencies, 95)
    summary["max_latency_ms"] = max(latencies) if latencies else 0.0
    return summary


def _logical_ids(result: dict[str, Any], k: int | None = None) -> list[str]:
    items = result.get("results", [])
    if k is not None:
        items = items[:k]
    return [item.get("logical_id", "") for item in items]


def _expected_ids(result: dict[str, Any]) -> set[str]:
    return set(result.get("expected_memory_ids", []))


def _hit_at(result: dict[str, Any], k: int) -> float:
    expected = _expected_ids(result)
    returned = set(_logical_ids(result, k))
    return 1.0 if expected & returned else 0.0


def _precision_at(result: dict[str, Any], k: int) -> float:
    if k <= 0:
        return 0.0
    expected = _expected_ids(result)
    returned = _logical_ids(result, k)
    return sum(1 for logical_id in returned if logical_id in expected) / k


def _reciprocal_rank(result: dict[str, Any]) -> float:
    expected = _expected_ids(result)
    for index, logical_id in enumerate(_logical_ids(result), start=1):
        if logical_id in expected:
            return 1.0 / index
    return 0.0


def _forbidden_hit(result: dict[str, Any]) -> float:
    forbidden = set(result.get("forbidden_memory_ids", []))
    returned = set(_logical_ids(result))
    return 1.0 if forbidden & returned else 0.0


def _average(values: Iterable[float]) -> float:
    items = list(values)
    return sum(items) / len(items) if items else 0.0


def _nearest_rank_percentile(sorted_values: list[float], percentile: int) -> float:
    if not sorted_values:
        return 0.0
    index = max(0, ceil((percentile / 100) * len(sorted_values)) - 1)
    return sorted_values[min(index, len(sorted_values) - 1)]
