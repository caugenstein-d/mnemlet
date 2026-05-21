"""Tests for benchmark metric calculations."""

import pytest

from mnemlet.benchmark.metrics import summarize_retrieval


def test_summarize_retrieval_calculates_hit_precision_and_mrr() -> None:
    query_results = [
        {
            "query_id": "q1",
            "expected_memory_ids": ["m1"],
            "forbidden_memory_ids": ["m3"],
            "no_hit": False,
            "results": [
                {"logical_id": "m1", "score": 0.9},
                {"logical_id": "m2", "score": 0.7},
            ],
            "latency_ms": 10.0,
        },
        {
            "query_id": "q2",
            "expected_memory_ids": ["m4"],
            "forbidden_memory_ids": [],
            "no_hit": False,
            "results": [
                {"logical_id": "m5", "score": 0.8},
                {"logical_id": "m4", "score": 0.6},
            ],
            "latency_ms": 30.0,
        },
    ]

    summary = summarize_retrieval(query_results, ks=(1, 3, 5))

    assert summary["hit_at_1"] == pytest.approx(0.5)
    assert summary["hit_at_3"] == pytest.approx(1.0)
    assert summary["mrr"] == pytest.approx(0.75)
    assert summary["precision_at_3"] == pytest.approx(2 / 6)
    assert summary["forbidden_hit_rate"] == pytest.approx(0.0)
    assert summary["p50_latency_ms"] == pytest.approx(20.0)
    assert summary["p95_latency_ms"] == pytest.approx(30.0)


def test_summarize_retrieval_counts_false_positives_for_no_hit_cases() -> None:
    query_results = [
        {
            "query_id": "q1",
            "expected_memory_ids": [],
            "forbidden_memory_ids": [],
            "no_hit": True,
            "results": [],
            "latency_ms": 5.0,
        },
        {
            "query_id": "q2",
            "expected_memory_ids": [],
            "forbidden_memory_ids": [],
            "no_hit": True,
            "results": [{"logical_id": "m1", "score": 0.4}],
            "latency_ms": 15.0,
        },
    ]

    summary = summarize_retrieval(query_results, ks=(1, 3, 5))

    assert summary["false_positive_rate"] == pytest.approx(0.5)
    assert summary["query_count"] == 2


def test_summarize_retrieval_accepts_canonical_result_keys() -> None:
    query_results = [
        {
            "query_id": "q1",
            "expected": ["m1"],
            "forbidden": ["m3"],
            "no_hit": False,
            "results": [
                {"logical_id": "m2", "score": 0.8},
                {"logical_id": "m1", "score": 0.7},
            ],
            "latency": 10.0,
        },
        {
            "query_id": "q2",
            "expected": ["m4"],
            "forbidden": ["m5"],
            "no_hit": False,
            "results": [
                {"logical_id": "m5", "score": 0.9},
                {"logical_id": "m4", "score": 0.6},
            ],
            "latency": 30.0,
        },
    ]

    summary = summarize_retrieval(query_results, ks=(1, 3, 5))

    assert summary["hit_at_3"] == pytest.approx(1.0)
    assert summary["mrr"] == pytest.approx(0.5)
    assert summary["forbidden_hit_rate"] == pytest.approx(0.5)
    assert summary["p50_latency_ms"] == pytest.approx(20.0)
    assert summary["p95_latency_ms"] == pytest.approx(30.0)
