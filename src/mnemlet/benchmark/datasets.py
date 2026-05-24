"""Load and validate benchmark datasets for memory retrieval evaluation."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


class BenchmarkDatasetError(ValueError):
    """Raised when a benchmark dataset is malformed."""


@dataclass(frozen=True)
class BenchmarkMemory:
    id: str
    content: str
    namespace: str
    importance: float = 0.5
    tags: list[str] = field(default_factory=list)
    status: str = "active"


@dataclass(frozen=True)
class BenchmarkQuery:
    id: str
    query: str
    namespace: str | None
    expected_memory_ids: list[str]
    forbidden_memory_ids: list[str] = field(default_factory=list)
    expected_substrings: list[str] = field(default_factory=list)
    expected_namespaces: list[str] = field(default_factory=list)
    min_expected_rank: int = 1
    no_hit: bool = False


@dataclass(frozen=True)
class BenchmarkCase:
    id: str
    category: str
    namespace: str
    memories: list[BenchmarkMemory]
    queries: list[BenchmarkQuery]


@dataclass(frozen=True)
class BenchmarkDataset:
    name: str
    cases: list[BenchmarkCase]

    @property
    def query_count(self) -> int:
        return sum(len(case.queries) for case in self.cases)


def resolve_dataset_path(dataset: str, root: Path | None = None) -> Path:
    base = root or Path.cwd()
    if dataset == "public":
        return base / "benchmarks/public/synthetic_memory_cases.json"
    if dataset == "private":
        return base / "benchmarks/private/real_world_cases.json"

    path = Path(dataset)
    if path.is_absolute():
        return path
    return base / path


def load_dataset(dataset: str, root: Path | None = None) -> BenchmarkDataset:
    return load_dataset_file(resolve_dataset_path(dataset, root=root))


def load_dataset_file(path: Path) -> BenchmarkDataset:
    payload = json.loads(path.read_text(encoding="utf-8"))
    return _parse_dataset(payload)


def _parse_dataset(payload: Any) -> BenchmarkDataset:
    if not isinstance(payload, dict):
        raise BenchmarkDatasetError("dataset root must be an object")

    name = _required_string(payload, "name", "dataset")
    raw_cases = payload.get("cases")
    if not isinstance(raw_cases, list) or not raw_cases:
        raise BenchmarkDatasetError("dataset cases must be a non-empty list")

    cases: list[BenchmarkCase] = []
    case_ids: set[str] = set()
    memory_ids: set[str] = set()
    query_ids: set[str] = set()
    for raw_case in raw_cases:
        if not isinstance(raw_case, dict):
            raise BenchmarkDatasetError("case must be an object")
        case_id = _required_string(raw_case, "id", "case")
        if case_id in case_ids:
            raise BenchmarkDatasetError(f"duplicate case id: {case_id}")
        case_ids.add(case_id)
        case = _parse_case(raw_case, memory_ids, query_ids)
        cases.append(case)

    return BenchmarkDataset(name=name, cases=cases)


def _parse_case(
    payload: Any, memory_ids: set[str], query_ids: set[str]
) -> BenchmarkCase:
    if not isinstance(payload, dict):
        raise BenchmarkDatasetError("case must be an object")

    case_id = _required_string(payload, "id", "case")
    category = _required_string(payload, "category", f"case {case_id}")
    namespace = _required_string(payload, "namespace", f"case {case_id}")

    raw_memories = payload.get("memories")
    if not isinstance(raw_memories, list) or not raw_memories:
        raise BenchmarkDatasetError(f"case {case_id} memories must be a non-empty list")
    memories = [
        _parse_memory(raw_memory, namespace, memory_ids) for raw_memory in raw_memories
    ]
    case_memory_ids = {memory.id for memory in memories}

    raw_queries = payload.get("queries")
    if not isinstance(raw_queries, list) or not raw_queries:
        raise BenchmarkDatasetError(f"case {case_id} queries must be a non-empty list")
    queries = [
        _parse_query(raw_query, namespace, case_memory_ids, query_ids)
        for raw_query in raw_queries
    ]

    return BenchmarkCase(
        id=case_id,
        category=category,
        namespace=namespace,
        memories=memories,
        queries=queries,
    )


def _parse_memory(
    payload: Any, case_namespace: str, memory_ids: set[str]
) -> BenchmarkMemory:
    if not isinstance(payload, dict):
        raise BenchmarkDatasetError("memory must be an object")

    memory_id = _required_string(payload, "id", "memory")
    if memory_id in memory_ids:
        raise BenchmarkDatasetError(f"duplicate memory id: {memory_id}")
    memory_ids.add(memory_id)

    content = _required_string(payload, "content", f"memory {memory_id}")
    namespace = payload.get("namespace", case_namespace)
    if not isinstance(namespace, str) or not namespace:
        raise BenchmarkDatasetError(f"memory {memory_id} namespace must be a non-empty string")

    importance = payload.get("importance", 0.5)
    if isinstance(importance, bool) or not isinstance(importance, int | float):
        raise BenchmarkDatasetError(f"memory {memory_id} importance must be numeric")
    if not 0 <= importance <= 1:
        raise BenchmarkDatasetError(f"memory {memory_id} importance must be between 0 and 1")

    tags = _string_list(payload.get("tags", []), f"memory {memory_id} tags")
    status = payload.get("status", "active")
    if status not in {"active", "cold_storage", "deleted"}:
        raise BenchmarkDatasetError(f"memory {memory_id} status is invalid")

    return BenchmarkMemory(
        id=memory_id,
        content=content,
        namespace=namespace,
        importance=float(importance),
        tags=tags,
        status=status,
    )


def _parse_query(
    payload: Any,
    case_namespace: str,
    case_memory_ids: set[str],
    query_ids: set[str],
) -> BenchmarkQuery:
    if not isinstance(payload, dict):
        raise BenchmarkDatasetError("query must be an object")

    query_id = _required_string(payload, "id", "query")
    if query_id in query_ids:
        raise BenchmarkDatasetError(f"duplicate query id: {query_id}")
    query_ids.add(query_id)

    query_text = _required_string(payload, "query", f"query {query_id}")
    namespace = payload.get("namespace", case_namespace)
    if namespace is not None and (not isinstance(namespace, str) or not namespace):
        raise BenchmarkDatasetError(f"query {query_id} namespace must be null or a non-empty string")

    expected_ids = _string_list(
        payload.get("expected_memory_ids", []), f"query {query_id} expected_memory_ids"
    )
    forbidden_ids = _string_list(
        payload.get("forbidden_memory_ids", []), f"query {query_id} forbidden_memory_ids"
    )
    expected_substrings = _string_list(
        payload.get("expected_substrings", []), f"query {query_id} expected_substrings"
    )
    expected_namespaces = _string_list(
        payload.get("expected_namespaces", []), f"query {query_id} expected_namespaces"
    )

    min_expected_rank = payload.get("min_expected_rank", 1)
    if (
        isinstance(min_expected_rank, bool)
        or not isinstance(min_expected_rank, int)
        or min_expected_rank < 1
    ):
        raise BenchmarkDatasetError(
            f"query {query_id} min_expected_rank must be a positive int"
        )

    no_hit = payload.get("no_hit", False)
    if not isinstance(no_hit, bool):
        raise BenchmarkDatasetError(f"query {query_id} no_hit must be a boolean")
    if no_hit and expected_ids:
        raise BenchmarkDatasetError(
            f"query {query_id} no_hit queries must not declare expected memory ids"
        )
    if not no_hit and not expected_ids and not expected_substrings:
        raise BenchmarkDatasetError(
            f"query {query_id} must declare expected ids/substrings or no_hit"
        )

    for memory_id in expected_ids:
        if memory_id not in case_memory_ids:
            raise BenchmarkDatasetError(f"unknown expected memory id: {memory_id}")
    for memory_id in forbidden_ids:
        if memory_id not in case_memory_ids:
            raise BenchmarkDatasetError(f"unknown forbidden memory id: {memory_id}")

    return BenchmarkQuery(
        id=query_id,
        query=query_text,
        namespace=namespace,
        expected_memory_ids=expected_ids,
        forbidden_memory_ids=forbidden_ids,
        expected_substrings=expected_substrings,
        expected_namespaces=expected_namespaces,
        min_expected_rank=min_expected_rank,
        no_hit=no_hit,
    )


def _required_string(payload: dict[str, Any], key: str, context: str) -> str:
    value = payload.get(key)
    if not isinstance(value, str) or not value:
        raise BenchmarkDatasetError(f"{context} {key} must be a non-empty string")
    return value


def _string_list(value: Any, context: str) -> list[str]:
    if not isinstance(value, list) or any(not isinstance(item, str) for item in value):
        raise BenchmarkDatasetError(f"{context} must be a list[str]")
    return value


@dataclass(frozen=True)
class QualityPhase:
    step: int
    action: str
    payload: dict[str, Any]


@dataclass(frozen=True)
class QualityScenario:
    id: str
    category: str
    description: str
    phases: list[QualityPhase]


@dataclass(frozen=True)
class QualityDataset:
    name: str
    version: int
    scenarios: list[QualityScenario]


def resolve_quality_dataset_path(dataset: str, root: Path | None = None) -> Path:
    base = root or Path.cwd()
    if dataset == "public":
        return base / "benchmarks/public/synthetic_quality_scenarios.json"
    if dataset == "private":
        return base / "benchmarks/private/real_quality_scenarios.json"
    path = Path(dataset)
    if path.is_absolute():
        return path
    return base / path


def load_quality_dataset(dataset: str, root: Path | None = None) -> QualityDataset:
    return load_quality_dataset_file(resolve_quality_dataset_path(dataset, root=root))


def load_quality_dataset_file(path: Path) -> QualityDataset:
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise BenchmarkDatasetError("quality dataset root must be an object")
    name = _required_string(payload, "name", "quality dataset")
    version = payload.get("version")
    if version != 1:
        raise BenchmarkDatasetError("quality dataset version must be 1")
    raw_scenarios = payload.get("scenarios")
    if not isinstance(raw_scenarios, list) or not raw_scenarios:
        raise BenchmarkDatasetError("quality dataset scenarios must be a non-empty list")
    scenarios = [_parse_quality_scenario(raw) for raw in raw_scenarios]
    return QualityDataset(name=name, version=version, scenarios=scenarios)


def _parse_quality_scenario(payload: Any) -> QualityScenario:
    if not isinstance(payload, dict):
        raise BenchmarkDatasetError("quality scenario must be an object")
    scenario_id = _required_string(payload, "id", "quality scenario")
    category = _required_string(payload, "category", f"quality scenario {scenario_id}")
    description = _required_string(payload, "description", f"quality scenario {scenario_id}")
    raw_phases = payload.get("phases")
    if not isinstance(raw_phases, list) or not raw_phases:
        raise BenchmarkDatasetError(f"quality scenario {scenario_id} phases must be a non-empty list")
    phases = [_parse_quality_phase(raw) for raw in raw_phases]
    return QualityScenario(scenario_id, category, description, phases)


def _parse_quality_phase(payload: Any) -> QualityPhase:
    if not isinstance(payload, dict):
        raise BenchmarkDatasetError("quality phase must be an object")
    step = payload.get("step")
    if isinstance(step, bool) or not isinstance(step, int) or step < 1:
        raise BenchmarkDatasetError("quality phase step must be a positive int")
    action = _required_string(payload, "action", "quality phase")
    return QualityPhase(step=step, action=action, payload={key: value for key, value in payload.items() if key not in {"step", "action"}})
