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
    forbidden_cases = [result for result in query_results if _forbidden_ids(result)]

    summary: dict[str, float | int] = {"query_count": len(query_results)}
    for k in k_values:
        summary[f"hit_at_{k}"] = _average(
            _hit_at(result, k) for result in regular_cases
        )
        summary[f"precision_at_{k}"] = _average(
            _precision_at(result, k) for result in regular_cases
        )

    summary["mrr"] = _average(_reciprocal_rank(result) for result in regular_cases)
    summary["min_expected_rank_rate"] = _average(
        _min_expected_rank_met(result) for result in regular_cases
    )
    summary["false_positive_rate"] = _average(
        1.0 if result.get("results") else 0.0 for result in no_hit_cases
    )
    summary["forbidden_hit_rate"] = _average(
        _forbidden_hit(result) for result in forbidden_cases
    )

    latencies = sorted(float(_latency(result)) for result in query_results)
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
    return set(result.get("expected_memory_ids", result.get("expected", [])))


def _expected_substrings(result: dict[str, Any]) -> list[str]:
    return list(result.get("expected_substrings", []))


def _expected_namespaces(result: dict[str, Any]) -> set[str]:
    return set(result.get("expected_namespaces", []))


def _forbidden_ids(result: dict[str, Any]) -> set[str]:
    return set(result.get("forbidden_memory_ids", result.get("forbidden", [])))


def _latency(result: dict[str, Any]) -> float:
    return float(result.get("latency_ms", result.get("latency", 0.0)))


def _hit_at(result: dict[str, Any], k: int) -> float:
    return 1.0 if _expected_match_ranks(result, k) else 0.0


def _precision_at(result: dict[str, Any], k: int) -> float:
    if k <= 0:
        return 0.0
    return len(_expected_match_ranks(result, k)) / k


def _reciprocal_rank(result: dict[str, Any]) -> float:
    ranks = _expected_match_ranks(result)
    if ranks:
        return 1.0 / ranks[0]
    return 0.0


def _min_expected_rank_met(result: dict[str, Any]) -> float:
    ranks = _expected_match_ranks(result)
    if not ranks:
        return 0.0
    min_expected_rank = int(result.get("min_expected_rank", 1))
    return 1.0 if ranks[0] <= min_expected_rank else 0.0


def _expected_match_ranks(result: dict[str, Any], k: int | None = None) -> list[int]:
    items = result.get("results", [])
    if k is not None:
        items = items[:k]
    return [index for index, item in enumerate(items, start=1) if _matches_expected(result, item)]


def _matches_expected(result: dict[str, Any], item: dict[str, Any]) -> bool:
    expected_ids = _expected_ids(result)
    expected_substrings = _expected_substrings(result)
    expected_namespaces = _expected_namespaces(result)
    namespace = str(item.get("namespace", ""))
    if expected_namespaces and namespace not in expected_namespaces:
        return False

    logical_id = str(item.get("logical_id", ""))
    if expected_ids and logical_id in expected_ids:
        return True

    content = str(item.get("content", ""))
    if expected_substrings and any(substring in content for substring in expected_substrings):
        return True

    return bool(expected_namespaces and not expected_ids and not expected_substrings)


def _forbidden_hit(result: dict[str, Any]) -> float:
    forbidden = _forbidden_ids(result)
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
