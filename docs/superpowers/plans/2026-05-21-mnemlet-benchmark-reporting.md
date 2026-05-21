# Mnémlet Benchmark Reporting Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Fix the Sleep Engine idle-loop bug and build a reproducible benchmark/reporting suite for public and private Mnémlet quality measurements.

**Architecture:** The Sleep Engine gets an activity-epoch based lifecycle so one idle period creates at most one consolidation run. Benchmarks run against isolated temporary Mnémlet storage, use public synthetic or private local datasets, compute retrieval/integration metrics, and emit JSON/Markdown/CSV reports. Adapter checks and live E2E checks are separated so `quick` remains stable while `full` can exercise OpenCode/OpenWebUI.

**Tech Stack:** Python 3.12, pytest, argparse, dataclasses, pathlib, tempfile, SQLite, ChromaDB, FastAPI ASGI test clients, optional subprocess calls to `opencode`, optional Node.js harness for OpenCode plugin checks.

---

## Required Pause Gates

After each task below:

1. Run the task's verification commands.
2. Report the exact evidence.
3. Commit the task if verification passes.
4. Stop and wait for Christoph to say `Weiter geht's`, `Go`, or equivalent.

Do not batch tasks across a pause gate.

## File Structure

### Existing files to modify

- Modify: `src/mnemlet/engine/sleep.py`
  - Responsibility: idle lifecycle, run state, checkpoint scoping, testable clock/cooldown injection.
- Modify: `src/mnemlet/server/routes/sleep.py`
  - Responsibility: expose richer sleep status while preserving existing route names.
- Modify: `src/mnemlet/__main__.py`
  - Responsibility: add `mnemlet benchmark ...` CLI commands.
- Modify: `.gitignore`
  - Responsibility: prevent private datasets and volatile benchmark results from being committed.
- Modify: `README.md`
  - Responsibility: add conservative benchmark section backed by generated reports.

### New source files

- Create: `src/mnemlet/benchmark/__init__.py`
  - Responsibility: package marker and public exports.
- Create: `src/mnemlet/benchmark/datasets.py`
  - Responsibility: dataclasses, JSON loading, validation, public/private path resolution.
- Create: `src/mnemlet/benchmark/runner.py`
  - Responsibility: isolated benchmark store creation, ingest mapping, query execution, raw result collection.
- Create: `src/mnemlet/benchmark/metrics.py`
  - Responsibility: retrieval and integration metric calculations.
- Create: `src/mnemlet/benchmark/reports.py`
  - Responsibility: JSON, Markdown, and CSV report writing plus environment metadata.
- Create: `src/mnemlet/benchmark/adapters.py`
  - Responsibility: REST, MCP, OpenWebUI filter, and OpenCode plugin adapter-level checks.
- Create: `src/mnemlet/benchmark/live.py`
  - Responsibility: optional live OpenCode/OpenWebUI checks for full mode.

### New benchmark data and tests

- Create: `benchmarks/public/synthetic_memory_cases.json`
  - Responsibility: commit-safe synthetic public dataset with 8 categories and 48 queries.
- Create: `benchmarks/private/.gitkeep`
  - Responsibility: keep private benchmark directory without tracking private data.
- Create: `benchmark-results/.gitkeep`
  - Responsibility: keep output directory without tracking volatile reports.
- Create: `tests/test_sleep.py`
  - Responsibility: Sleep Engine lifecycle regression tests.
- Create: `tests/test_benchmark_datasets.py`
  - Responsibility: dataset validation tests.
- Create: `tests/test_benchmark_metrics.py`
  - Responsibility: deterministic metric calculation tests.
- Create: `tests/test_benchmark_runner.py`
  - Responsibility: isolated runner tests.
- Create: `tests/test_benchmark_reports.py`
  - Responsibility: report generation tests.
- Create: `tests/test_benchmark_cli.py`
  - Responsibility: CLI parser and benchmark command smoke tests.
- Create: `tests/test_benchmark_adapters.py`
  - Responsibility: adapter-level behavior tests with local fakes.

---

## Task 1: Fix Sleep Engine idle lifecycle

**Files:**
- Create: `tests/test_sleep.py`
- Modify: `src/mnemlet/engine/sleep.py`
- Modify: `src/mnemlet/server/routes/sleep.py`

- [ ] **Step 1: Write failing Sleep Engine lifecycle tests**

Create `tests/test_sleep.py` with this content:

```python
"""Tests for the Sleep Engine idle lifecycle."""

from collections.abc import Callable

from mnemlet.engine.sleep import SleepEngine


class FakeClock:
    """Controllable monotonic-style clock for sleep tests."""

    def __init__(self, now: float = 1_000.0) -> None:
        self.now = now

    def __call__(self) -> float:
        return self.now

    def advance(self, seconds: float) -> None:
        self.now += seconds


class FastSleepEngine(SleepEngine):
    """SleepEngine with deterministic no-op tasks for fast tests."""

    def __init__(self, clock: Callable[[], float], threshold: int = 10) -> None:
        super().__init__(
            db=None,
            chroma=None,
            embedder=None,
            vault=None,
            decay_engine=None,
            inactivity_threshold_seconds=threshold,
            clock=clock,
            task_cooldown_seconds=0,
        )
        self.task_runs: list[str] = []

    def _tasks(self):
        return [self._task_one, self._task_two]

    def _task_one(self) -> None:
        self.task_runs.append("one")

    def _task_two(self) -> None:
        self.task_runs.append("two")


def wait_for_engine(engine: SleepEngine) -> None:
    """Wait for the engine's background thread to finish."""
    assert engine._thread is not None
    engine._thread.join(timeout=2)
    assert not engine._thread.is_alive()


def test_should_sleep_after_inactivity_threshold() -> None:
    clock = FakeClock()
    engine = FastSleepEngine(clock=clock, threshold=10)

    assert engine.should_sleep() is False
    clock.advance(11)

    assert engine.should_sleep() is True


def test_completed_run_does_not_immediately_sleep_again() -> None:
    clock = FakeClock()
    engine = FastSleepEngine(clock=clock, threshold=10)
    clock.advance(11)

    assert engine.start() == {"status": "started"}
    wait_for_engine(engine)

    assert engine.state == "completed"
    assert engine.should_sleep() is False
    assert engine.task_runs == ["one", "two"]


def test_new_activity_allows_future_sleep_cycle() -> None:
    clock = FakeClock()
    engine = FastSleepEngine(clock=clock, threshold=10)
    clock.advance(11)
    engine.start()
    wait_for_engine(engine)

    engine.bump_activity()
    assert engine.state == "idle"
    assert engine.should_sleep() is False

    clock.advance(11)
    assert engine.should_sleep() is True


def test_checkpoints_are_scoped_to_each_run() -> None:
    clock = FakeClock()
    engine = FastSleepEngine(clock=clock, threshold=10)
    clock.advance(11)
    engine.start()
    wait_for_engine(engine)

    engine.bump_activity()
    clock.advance(11)
    engine.start()
    wait_for_engine(engine)

    assert engine.task_runs == ["one", "two", "one", "two"]


def test_parallel_runs_are_prevented_even_when_force_is_true() -> None:
    clock = FakeClock()
    engine = FastSleepEngine(clock=clock, threshold=10)
    clock.advance(11)

    assert engine.start() == {"status": "started"}
    assert engine.start(force=True) == {"status": "already_running"}

    wait_for_engine(engine)


def test_start_reports_not_ready_before_threshold() -> None:
    clock = FakeClock()
    engine = FastSleepEngine(clock=clock, threshold=10)

    assert engine.start() == {"status": "not_ready", "state": "idle"}
    assert engine._thread is None


def test_force_start_runs_before_threshold() -> None:
    clock = FakeClock()
    engine = FastSleepEngine(clock=clock, threshold=10)

    assert engine.start(force=True) == {"status": "started"}
    wait_for_engine(engine)

    assert engine.task_runs == ["one", "two"]
```

- [ ] **Step 2: Run Sleep Engine tests and verify they fail**

Run:

```bash
/home/christoph/mnemlet/.venv/bin/python -m pytest tests/test_sleep.py -q
```

Expected before implementation: failures mentioning unexpected keyword arguments `clock` or `task_cooldown_seconds`, and missing `_tasks` override support.

- [ ] **Step 3: Implement the Sleep Engine lifecycle fix**

Replace `src/mnemlet/engine/sleep.py` with this implementation, preserving task behavior while adding testable lifecycle control:

```python
"""Sleep Engine — night consolidation during user inactivity."""

import threading
import time
from collections.abc import Callable, Sequence
from datetime import datetime, timezone
from typing import Any


class SleepEngine:
    """Orchestrates memory consolidation during user inactivity.

    Runs in a background thread. A single activity epoch can trigger at most one
    automatic consolidation run. New API activity starts a new epoch and allows
    a future run after the inactivity threshold is reached again.
    """

    def __init__(
        self,
        db: Any,
        chroma: Any,
        embedder: Any,
        vault: Any,
        decay_engine: Any = None,
        inactivity_threshold_seconds: int = 7200,
        clock: Callable[[], float] | None = None,
        task_cooldown_seconds: float = 30.0,
    ) -> None:
        self.db = db
        self.chroma = chroma
        self.embedder = embedder
        self.vault = vault
        self.decay = decay_engine
        self.inactivity_threshold = inactivity_threshold_seconds
        self._clock = clock or time.time
        self._task_cooldown_seconds = task_cooldown_seconds
        self._last_activity = self._clock()
        self._last_completed_at: float | None = None
        self._activity_epoch = 0
        self._completed_epoch: int | None = None
        self._running = False
        self._paused = False
        self._thread: threading.Thread | None = None
        self._checkpoint: dict[str, bool] = {}
        self._lock = threading.Lock()

    def bump_activity(self) -> None:
        """Record API activity and enable a future sleep cycle."""
        with self._lock:
            self._last_activity = self._clock()
            self._activity_epoch += 1

    @property
    def state(self) -> str:
        """Current sleep engine state."""
        if self._paused:
            return "paused"
        if self._running:
            return "running"
        if self._completed_epoch == self._activity_epoch and self._last_completed_at is not None:
            return "completed"
        return "idle"

    @property
    def idle_seconds(self) -> float:
        """Seconds since last activity."""
        return max(0.0, self._clock() - self._last_activity)

    @property
    def last_completed_at(self) -> float | None:
        """Unix timestamp for the last completed consolidation run."""
        return self._last_completed_at

    @property
    def checkpoint(self) -> dict[str, bool]:
        """Return a copy of the current run checkpoint state."""
        return dict(self._checkpoint)

    def should_sleep(self) -> bool:
        """Check whether an automatic sleep phase should start."""
        if self._running or self._paused:
            return False
        if self._completed_epoch == self._activity_epoch:
            return False
        return self.idle_seconds >= self.inactivity_threshold

    def start(self, force: bool = False) -> dict:
        """Start consolidation in a background thread."""
        with self._lock:
            if self._running:
                return {"status": "already_running"}
            if not force and not self.should_sleep():
                return {"status": "not_ready", "state": self.state}

            self._checkpoint = {}
            self._running = True
            self._paused = False
            self._thread = threading.Thread(target=self._run_loop, daemon=True)
            self._thread.start()
            return {"status": "started"}

    def stop(self) -> dict:
        """Gracefully stop the sleep engine."""
        self._running = False
        self._paused = False
        if self._thread and self._thread.is_alive():
            self._thread.join(timeout=30)
        return {"status": "stopped", "checkpoint": self.checkpoint}

    def status(self) -> dict:
        """Return structured sleep engine status for API responses."""
        return {
            "state": self.state,
            "idle_seconds": self.idle_seconds,
            "inactivity_threshold_seconds": self.inactivity_threshold,
            "last_completed_at": self._last_completed_at,
            "activity_epoch": self._activity_epoch,
            "completed_epoch": self._completed_epoch,
            "checkpoint": self.checkpoint,
        }

    def _tasks(self) -> Sequence[Callable[[], None]]:
        """Return consolidation tasks in execution order."""
        return [
            self._task_dedup_today,
            self._task_rescore_stale,
            self._task_cluster_similar,
            self._task_prepare_briefing,
        ]

    def _run_loop(self) -> None:
        """Main sleep loop — run consolidation tasks sequentially."""
        completed = False
        try:
            completed = self._run_tasks()
        finally:
            with self._lock:
                self._running = False
                if completed:
                    now = self._clock()
                    self._last_completed_at = now
                    self._last_activity = now
                    self._completed_epoch = self._activity_epoch
            print("[sleep] Consolidation complete")

    def _run_tasks(self) -> bool:
        """Run consolidation tasks and return True when all tasks finished."""
        for task in self._tasks():
            if not self._running:
                return False
            task_name = task.__name__
            try:
                print(f"[sleep] Running: {task_name}")
                task()
                self._checkpoint[task_name] = True
            except Exception as e:
                print(f"[sleep] Task {task_name} failed: {e}")
                self._checkpoint[task_name] = False

            if self._task_cooldown_seconds > 0:
                time.sleep(self._task_cooldown_seconds)
        return True

    def _task_dedup_today(self) -> None:
        """Find and merge near-duplicate memories created today."""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        rows = self.db.conn.execute(
            """SELECT id, content_preview, namespace FROM memories
               WHERE status = 'active' AND created_at >= ?
               ORDER BY created_at DESC LIMIT 200""",
            (today,),
        ).fetchall()

        seen = {}
        for row in rows:
            key = row["content_preview"][:80]
            ns = row["namespace"]
            if (ns, key) in seen:
                self.db.conn.execute(
                    "UPDATE memories SET status = 'cold_storage', retention_score = 0.02 WHERE id = ?",
                    (row["id"],),
                )
                print(f"[sleep] Dedup: moved {row['id'][:8]} to cold (dup of {seen[(ns, key)][:8]})")
            else:
                seen[(ns, key)] = row["id"]

        self.db.conn.commit()

    def _task_rescore_stale(self) -> None:
        """Apply decay to stale memories and run purge."""
        if self.decay:
            result = self.decay.decay_all_active(limit=500)
            print(
                f"[sleep] Rescore: processed {result['processed']}, "
                f"decayed {result['decayed']}, "
                f"cold={result['moved_to_cold']}, deleted={result['hard_deleted']}"
            )

    def _task_cluster_similar(self) -> None:
        """Group semantically similar memories from today."""
        today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
        rows = self.db.conn.execute(
            """SELECT id, content_preview, namespace, retention_score
               FROM memories WHERE status = 'active' AND created_at >= ?
               LIMIT 100""",
            (today,),
        ).fetchall()

        if len(rows) < 3:
            return

        from collections import Counter

        ns_counts = Counter(r["namespace"] for r in rows)
        for ns, count in ns_counts.most_common(5):
            print(f"[sleep] Cluster: namespace '{ns}' has {count} new memories today")

    def _task_prepare_briefing(self) -> None:
        """Generate a morning briefing from top-scored recent memories."""
        rows = self.db.conn.execute(
            """SELECT content_preview, namespace, retention_score
               FROM memories WHERE status = 'active'
               ORDER BY retention_score DESC LIMIT 10"""
        ).fetchall()

        if not rows:
            return

        lines = ["# Morning Briefing", "", f"Generated: {datetime.now(timezone.utc).isoformat()}", ""]
        for r in rows:
            lines.append(f"- [{r['namespace']}] (score: {r['retention_score']:.2f}) {r['content_preview'][:100]}")

        briefing = "\n".join(lines)
        now = datetime.now(timezone.utc).isoformat()

        import uuid

        bid = str(uuid.uuid4())[:8]
        self.db.conn.execute(
            """INSERT INTO memories (id, namespace, content_preview, retention_score,
               importance, created_at, last_accessed_at, status)
               VALUES (?, '__system__/morning_briefing', ?, 0.9, 0.8, ?, ?, 'active')""",
            (f"briefing-{bid}", briefing[:200], now, now),
        )
        self.db.conn.commit()

        if self.vault:
            self.vault.write_memory(
                memory_id=f"briefing-{bid}",
                namespace="__system__/morning_briefing",
                content=briefing,
                retention_score=0.9,
                created_at=now,
            )

        print("[sleep] Morning briefing generated")
```

- [ ] **Step 4: Update sleep route status response**

Replace `src/mnemlet/server/routes/sleep.py` with this content:

```python
"""Sleep Engine control routes."""

from fastapi import APIRouter, Request


router = APIRouter(prefix="/api/v1/sleep", tags=["sleep"])


@router.get("/status")
async def sleep_status(request: Request) -> dict:
    """Get sleep engine status."""
    engine = request.app.state.sleep_engine
    return engine.status()


@router.post("/start")
async def sleep_start(request: Request) -> dict:
    """Manually start sleep consolidation."""
    engine = request.app.state.sleep_engine
    return engine.start(force=True)


@router.post("/stop")
async def sleep_stop(request: Request) -> dict:
    """Stop sleep consolidation."""
    engine = request.app.state.sleep_engine
    return engine.stop()
```

- [ ] **Step 5: Run focused Sleep Engine tests**

Run:

```bash
/home/christoph/mnemlet/.venv/bin/python -m pytest tests/test_sleep.py -q
```

Expected: all tests in `tests/test_sleep.py` pass.

- [ ] **Step 6: Run API and full test suite**

Run:

```bash
/home/christoph/mnemlet/.venv/bin/python -m pytest tests/test_api.py tests/test_sleep.py -q
/home/christoph/mnemlet/.venv/bin/python -m pytest -q
```

Expected: all tests pass. Existing ChromaDB deprecation warnings are acceptable.

- [ ] **Step 7: Commit Sleep Engine fix**

Run:

```bash
git status --short
git add src/mnemlet/engine/sleep.py src/mnemlet/server/routes/sleep.py tests/test_sleep.py
git commit -m "fix: prevent repeated sleep consolidation"
```

Pause gate: report test output and commit hash, then wait.

---

## Task 2: Add benchmark dataset model and public/private directories

**Files:**
- Create: `src/mnemlet/benchmark/__init__.py`
- Create: `src/mnemlet/benchmark/datasets.py`
- Create: `benchmarks/public/synthetic_memory_cases.json`
- Create: `benchmarks/private/.gitkeep`
- Create: `benchmark-results/.gitkeep`
- Modify: `.gitignore`
- Create: `tests/test_benchmark_datasets.py`

- [ ] **Step 1: Write failing dataset validation tests**

Create `tests/test_benchmark_datasets.py`:

```python
"""Tests for benchmark dataset loading and validation."""

import json
from pathlib import Path

import pytest

from mnemlet.benchmark.datasets import (
    BenchmarkDatasetError,
    load_dataset,
    load_dataset_file,
    resolve_dataset_path,
)


def write_json(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload), encoding="utf-8")


def valid_payload() -> dict:
    return {
        "name": "unit",
        "cases": [
            {
                "id": "case_one",
                "category": "exact_fact",
                "namespace": "prefs",
                "memories": [
                    {"id": "memory_dark", "content": "User prefers dark mode.", "importance": 0.9},
                    {"id": "memory_light", "content": "The office has bright lights.", "importance": 0.3},
                ],
                "queries": [
                    {
                        "id": "query_dark",
                        "query": "What editor theme does the user prefer?",
                        "expected_memory_ids": ["memory_dark"],
                        "forbidden_memory_ids": ["memory_light"],
                        "min_expected_rank": 1,
                    }
                ],
            }
        ],
    }


def test_load_dataset_file_accepts_valid_payload(tmp_path: Path) -> None:
    path = tmp_path / "dataset.json"
    write_json(path, valid_payload())

    dataset = load_dataset_file(path)

    assert dataset.name == "unit"
    assert dataset.cases[0].id == "case_one"
    assert dataset.cases[0].queries[0].expected_memory_ids == ["memory_dark"]


def test_load_dataset_file_rejects_duplicate_memory_ids(tmp_path: Path) -> None:
    payload = valid_payload()
    payload["cases"][0]["memories"].append(
        {"id": "memory_dark", "content": "Duplicate logical ID.", "importance": 0.5}
    )
    path = tmp_path / "dataset.json"
    write_json(path, payload)

    with pytest.raises(BenchmarkDatasetError, match="duplicate memory id"):
        load_dataset_file(path)


def test_load_dataset_file_rejects_unknown_expected_id(tmp_path: Path) -> None:
    payload = valid_payload()
    payload["cases"][0]["queries"][0]["expected_memory_ids"] = ["missing"]
    path = tmp_path / "dataset.json"
    write_json(path, payload)

    with pytest.raises(BenchmarkDatasetError, match="unknown expected memory id"):
        load_dataset_file(path)


def test_load_dataset_file_rejects_empty_no_hit_without_marker(tmp_path: Path) -> None:
    payload = valid_payload()
    payload["cases"][0]["queries"][0]["expected_memory_ids"] = []
    path = tmp_path / "dataset.json"
    write_json(path, payload)

    with pytest.raises(BenchmarkDatasetError, match="no_hit"):
        load_dataset_file(path)


def test_resolve_dataset_path_public_and_private(tmp_path: Path) -> None:
    public_path = resolve_dataset_path("public", root=tmp_path)
    private_path = resolve_dataset_path("private", root=tmp_path)

    assert public_path == tmp_path / "benchmarks" / "public" / "synthetic_memory_cases.json"
    assert private_path == tmp_path / "benchmarks" / "private" / "real_world_cases.json"


def test_load_dataset_public_fixture() -> None:
    dataset = load_dataset("public", root=Path.cwd())

    assert dataset.name == "public-synthetic"
    assert len(dataset.cases) == 8
    assert sum(len(case.queries) for case in dataset.cases) == 48
```

- [ ] **Step 2: Run dataset tests and verify they fail**

Run:

```bash
/home/christoph/mnemlet/.venv/bin/python -m pytest tests/test_benchmark_datasets.py -q
```

Expected: import failure for `mnemlet.benchmark.datasets`.

- [ ] **Step 3: Create benchmark package exports**

Create `src/mnemlet/benchmark/__init__.py`:

```python
"""Benchmarking utilities for Mnémlet quality reports."""

from mnemlet.benchmark.datasets import BenchmarkCase, BenchmarkDataset, BenchmarkMemory, BenchmarkQuery

__all__ = ["BenchmarkCase", "BenchmarkDataset", "BenchmarkMemory", "BenchmarkQuery"]
```

- [ ] **Step 4: Implement dataset dataclasses and validation**

Create `src/mnemlet/benchmark/datasets.py`:

```python
"""Benchmark dataset loading and validation."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


class BenchmarkDatasetError(ValueError):
    """Raised when a benchmark dataset is invalid."""


@dataclass(frozen=True)
class BenchmarkMemory:
    """A logical memory in a benchmark dataset."""

    id: str
    content: str
    namespace: str
    importance: float = 0.5
    tags: list[str] = field(default_factory=list)
    status: str = "active"


@dataclass(frozen=True)
class BenchmarkQuery:
    """A benchmark query and its expected retrieval behavior."""

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
    """A grouped benchmark scenario."""

    id: str
    category: str
    namespace: str
    memories: list[BenchmarkMemory]
    queries: list[BenchmarkQuery]


@dataclass(frozen=True)
class BenchmarkDataset:
    """A complete benchmark dataset."""

    name: str
    cases: list[BenchmarkCase]

    @property
    def query_count(self) -> int:
        """Return the number of queries in this dataset."""
        return sum(len(case.queries) for case in self.cases)


def resolve_dataset_path(dataset: str, root: Path | None = None) -> Path:
    """Resolve the configured path for a named dataset."""
    base = root or Path.cwd()
    if dataset == "public":
        return base / "benchmarks" / "public" / "synthetic_memory_cases.json"
    if dataset == "private":
        return base / "benchmarks" / "private" / "real_world_cases.json"
    candidate = Path(dataset)
    return candidate if candidate.is_absolute() else base / candidate


def load_dataset(dataset: str, root: Path | None = None) -> BenchmarkDataset:
    """Load a named benchmark dataset."""
    return load_dataset_file(resolve_dataset_path(dataset, root=root))


def load_dataset_file(path: Path) -> BenchmarkDataset:
    """Load and validate a benchmark dataset JSON file."""
    if not path.exists():
        raise BenchmarkDatasetError(f"dataset file does not exist: {path}")
    payload = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(payload, dict):
        raise BenchmarkDatasetError("dataset root must be an object")
    name = _required_str(payload, "name", "dataset")
    raw_cases = payload.get("cases")
    if not isinstance(raw_cases, list) or not raw_cases:
        raise BenchmarkDatasetError("dataset cases must be a non-empty list")

    cases = [_parse_case(raw_case) for raw_case in raw_cases]
    _validate_dataset(cases)
    return BenchmarkDataset(name=name, cases=cases)


def _parse_case(raw: Any) -> BenchmarkCase:
    if not isinstance(raw, dict):
        raise BenchmarkDatasetError("case must be an object")
    case_id = _required_str(raw, "id", "case")
    category = _required_str(raw, "category", case_id)
    namespace = _required_str(raw, "namespace", case_id)
    raw_memories = raw.get("memories")
    raw_queries = raw.get("queries")
    if not isinstance(raw_memories, list) or not raw_memories:
        raise BenchmarkDatasetError(f"case {case_id} memories must be a non-empty list")
    if not isinstance(raw_queries, list) or not raw_queries:
        raise BenchmarkDatasetError(f"case {case_id} queries must be a non-empty list")
    memories = [_parse_memory(item, namespace) for item in raw_memories]
    queries = [_parse_query(item, namespace, category) for item in raw_queries]
    return BenchmarkCase(id=case_id, category=category, namespace=namespace, memories=memories, queries=queries)


def _parse_memory(raw: Any, default_namespace: str) -> BenchmarkMemory:
    if not isinstance(raw, dict):
        raise BenchmarkDatasetError("memory must be an object")
    memory_id = _required_str(raw, "id", "memory")
    content = _required_str(raw, "content", memory_id)
    namespace = _optional_str(raw, "namespace") or default_namespace
    importance = float(raw.get("importance", 0.5))
    if importance < 0.0 or importance > 1.0:
        raise BenchmarkDatasetError(f"memory {memory_id} importance must be between 0 and 1")
    tags = raw.get("tags", [])
    if not isinstance(tags, list) or not all(isinstance(tag, str) for tag in tags):
        raise BenchmarkDatasetError(f"memory {memory_id} tags must be a list of strings")
    status = raw.get("status", "active")
    if status not in {"active", "cold_storage", "deleted"}:
        raise BenchmarkDatasetError(f"memory {memory_id} status is invalid: {status}")
    return BenchmarkMemory(
        id=memory_id,
        content=content,
        namespace=namespace,
        importance=importance,
        tags=tags,
        status=status,
    )


def _parse_query(raw: Any, default_namespace: str, category: str) -> BenchmarkQuery:
    if not isinstance(raw, dict):
        raise BenchmarkDatasetError("query must be an object")
    query_id = _required_str(raw, "id", "query")
    text = _required_str(raw, "query", query_id)
    namespace = raw.get("namespace", default_namespace)
    if namespace is not None and not isinstance(namespace, str):
        raise BenchmarkDatasetError(f"query {query_id} namespace must be a string or null")
    expected = _string_list(raw, "expected_memory_ids", default=[])
    forbidden = _string_list(raw, "forbidden_memory_ids", default=[])
    substrings = _string_list(raw, "expected_substrings", default=[])
    namespaces = _string_list(raw, "expected_namespaces", default=[])
    min_rank = int(raw.get("min_expected_rank", 1))
    no_hit = bool(raw.get("no_hit", category == "no_hit"))
    return BenchmarkQuery(
        id=query_id,
        query=text,
        namespace=namespace,
        expected_memory_ids=expected,
        forbidden_memory_ids=forbidden,
        expected_substrings=substrings,
        expected_namespaces=namespaces,
        min_expected_rank=min_rank,
        no_hit=no_hit,
    )


def _validate_dataset(cases: list[BenchmarkCase]) -> None:
    memory_ids: set[str] = set()
    query_ids: set[str] = set()
    for case in cases:
        case_memory_ids = {memory.id for memory in case.memories}
        for memory in case.memories:
            if memory.id in memory_ids:
                raise BenchmarkDatasetError(f"duplicate memory id: {memory.id}")
            memory_ids.add(memory.id)
        for query in case.queries:
            if query.id in query_ids:
                raise BenchmarkDatasetError(f"duplicate query id: {query.id}")
            query_ids.add(query.id)
            if not query.expected_memory_ids and not query.no_hit and not query.expected_substrings:
                raise BenchmarkDatasetError(f"query {query.id} has no expected memories and is not marked no_hit")
            for memory_id in query.expected_memory_ids:
                if memory_id not in case_memory_ids:
                    raise BenchmarkDatasetError(f"query {query.id} references unknown expected memory id: {memory_id}")
            for memory_id in query.forbidden_memory_ids:
                if memory_id not in case_memory_ids:
                    raise BenchmarkDatasetError(f"query {query.id} references unknown forbidden memory id: {memory_id}")


def _required_str(raw: dict[str, Any], key: str, owner: str) -> str:
    value = raw.get(key)
    if not isinstance(value, str) or not value.strip():
        raise BenchmarkDatasetError(f"{owner} requires non-empty string field {key}")
    return value


def _optional_str(raw: dict[str, Any], key: str) -> str | None:
    value = raw.get(key)
    if value is None:
        return None
    if not isinstance(value, str):
        raise BenchmarkDatasetError(f"optional field {key} must be a string")
    return value


def _string_list(raw: dict[str, Any], key: str, default: list[str]) -> list[str]:
    value = raw.get(key, default)
    if not isinstance(value, list) or not all(isinstance(item, str) for item in value):
        raise BenchmarkDatasetError(f"field {key} must be a list of strings")
    return value
```

- [ ] **Step 5: Add public synthetic dataset with 8 categories and 48 queries**

Create `benchmarks/public/synthetic_memory_cases.json` by running this exact one-off generator from the repository root:

```bash
/home/christoph/mnemlet/.venv/bin/python - <<'PY'
import json
from pathlib import Path

cases = [
    {
        "id": "exact_fact_agent_preferences",
        "category": "exact_fact",
        "namespace": "preferences",
        "memories": [
            {"id": "memory_pref_dark_mode", "content": "Christoph prefers dark mode in editors and dashboards.", "importance": 0.9},
            {"id": "memory_pref_zsh", "content": "Christoph's preferred shell on development machines is zsh.", "importance": 0.8},
            {"id": "memory_pref_python312", "content": "Mnémlet development targets Python 3.12 or newer.", "importance": 0.85},
            {"id": "memory_pref_local_first", "content": "For AI infrastructure, Christoph strongly prefers self-hosted local-first tools over SaaS.", "importance": 0.95},
            {"id": "memory_pref_notes", "content": "Project notes should use clear date-prefixed Markdown filenames.", "importance": 0.65},
            {"id": "memory_pref_noise", "content": "The office coffee grinder has a conical burr mechanism.", "importance": 0.2},
        ],
        "queries": [
            {"id": "q_exact_dark_mode", "query": "Which editor theme does Christoph prefer?", "expected_memory_ids": ["memory_pref_dark_mode"], "forbidden_memory_ids": ["memory_pref_noise"], "min_expected_rank": 1},
            {"id": "q_exact_shell", "query": "What shell does Christoph prefer on dev machines?", "expected_memory_ids": ["memory_pref_zsh"], "min_expected_rank": 1},
            {"id": "q_exact_python", "query": "Which Python version does Mnémlet target?", "expected_memory_ids": ["memory_pref_python312"], "min_expected_rank": 1},
            {"id": "q_exact_local_first", "query": "Does Christoph prefer SaaS or self-hosted local AI tooling?", "expected_memory_ids": ["memory_pref_local_first"], "min_expected_rank": 1},
            {"id": "q_exact_notes", "query": "How should project notes be named?", "expected_memory_ids": ["memory_pref_notes"], "min_expected_rank": 1},
            {"id": "q_exact_dark_distractor", "query": "What preference affects dashboards and editors?", "expected_memory_ids": ["memory_pref_dark_mode"], "forbidden_memory_ids": ["memory_pref_noise"], "min_expected_rank": 2},
        ],
    },
    {
        "id": "paraphrase_project_stack",
        "category": "paraphrase",
        "namespace": "projects/mnemlet",
        "memories": [
            {"id": "memory_stack_fastapi", "content": "Mnémlet exposes its HTTP API through FastAPI routes.", "importance": 0.8},
            {"id": "memory_stack_sqlite", "content": "Mnémlet stores metadata, scores, and interactions in SQLite.", "importance": 0.8},
            {"id": "memory_stack_chroma", "content": "Mnémlet uses ChromaDB for vector search over memory content.", "importance": 0.8},
            {"id": "memory_stack_embeddings", "content": "Mnémlet embeddings run locally with an ONNX MiniLM model.", "importance": 0.75},
            {"id": "memory_stack_mcp", "content": "Mnémlet exposes memory tools to agents through an MCP server.", "importance": 0.85},
            {"id": "memory_stack_noise", "content": "Static website assets are served separately from the memory engine.", "importance": 0.25},
        ],
        "queries": [
            {"id": "q_para_http", "query": "What framework serves Mnémlet's web endpoints?", "expected_memory_ids": ["memory_stack_fastapi"], "min_expected_rank": 2},
            {"id": "q_para_metadata", "query": "Where are memory scores and interaction rows kept?", "expected_memory_ids": ["memory_stack_sqlite"], "min_expected_rank": 2},
            {"id": "q_para_vectors", "query": "Which component handles semantic vector lookup?", "expected_memory_ids": ["memory_stack_chroma"], "min_expected_rank": 2},
            {"id": "q_para_local_embeddings", "query": "How are text embeddings generated without a cloud API?", "expected_memory_ids": ["memory_stack_embeddings"], "min_expected_rank": 3},
            {"id": "q_para_agent_tools", "query": "How do coding agents access Mnémlet tools?", "expected_memory_ids": ["memory_stack_mcp"], "min_expected_rank": 2},
            {"id": "q_para_storage_pair", "query": "Which storage pieces combine SQL metadata with vector search?", "expected_memory_ids": ["memory_stack_sqlite", "memory_stack_chroma"], "min_expected_rank": 3},
        ],
    },
    {
        "id": "namespace_isolation_tools",
        "category": "namespace_isolation",
        "namespace": "projects/mnemlet",
        "memories": [
            {"id": "memory_ns_mnemlet_mcp", "namespace": "projects/mnemlet", "content": "In Mnémlet, MCP means Model Context Protocol integration for memory tools.", "importance": 0.8},
            {"id": "memory_ns_mnemlet_filter", "namespace": "projects/mnemlet", "content": "The Mnémlet OpenWebUI integration uses a filter named Mnémlet Memory.", "importance": 0.8},
            {"id": "memory_ns_ari_mcp", "namespace": "projects/ari", "content": "In Ari's project notes, MCP refers to a music control prototype.", "importance": 0.4},
            {"id": "memory_ns_ari_filter", "namespace": "projects/ari", "content": "Ari uses Discord behavior filters for Sarah's assistant setup.", "importance": 0.4},
            {"id": "memory_ns_personal_filter", "namespace": "personal/preferences", "content": "Coffee filters should be rinsed before brewing.", "importance": 0.3},
            {"id": "memory_ns_noise", "namespace": "projects/mnemlet", "content": "The launch page includes a brain SVG animation.", "importance": 0.3},
        ],
        "queries": [
            {"id": "q_ns_mcp_mnemlet", "namespace": "projects/mnemlet", "query": "What does MCP mean in the Mnémlet project?", "expected_memory_ids": ["memory_ns_mnemlet_mcp"], "forbidden_memory_ids": ["memory_ns_ari_mcp"], "min_expected_rank": 1},
            {"id": "q_ns_filter_mnemlet", "namespace": "projects/mnemlet", "query": "What is the OpenWebUI filter called?", "expected_memory_ids": ["memory_ns_mnemlet_filter"], "forbidden_memory_ids": ["memory_ns_personal_filter"], "min_expected_rank": 1},
            {"id": "q_ns_mcp_ari", "namespace": "projects/ari", "query": "What does MCP refer to in Ari notes?", "expected_memory_ids": ["memory_ns_ari_mcp"], "forbidden_memory_ids": ["memory_ns_mnemlet_mcp"], "min_expected_rank": 1},
            {"id": "q_ns_filter_ari", "namespace": "projects/ari", "query": "Which filters are mentioned for Ari?", "expected_memory_ids": ["memory_ns_ari_filter"], "forbidden_memory_ids": ["memory_ns_mnemlet_filter"], "min_expected_rank": 1},
            {"id": "q_ns_filter_personal", "namespace": "personal/preferences", "query": "What should happen before brewing coffee?", "expected_memory_ids": ["memory_ns_personal_filter"], "forbidden_memory_ids": ["memory_ns_mnemlet_filter"], "min_expected_rank": 1},
            {"id": "q_ns_mnemlet_animation", "namespace": "projects/mnemlet", "query": "Which visual asset is on the launch page?", "expected_memory_ids": ["memory_ns_noise"], "min_expected_rank": 2},
        ],
    },
    {
        "id": "distractor_resistance_codename",
        "category": "distractor_resistance",
        "namespace": "integration/sentinel",
        "memories": [
            {"id": "memory_bridge_codename", "content": "Christoph calls the Mnémlet OpenCode bridge Nebelkrähe.", "importance": 0.95},
            {"id": "memory_bridge_arch", "content": "A stone bridge crosses the Nebel valley near an old hiking path.", "importance": 0.2},
            {"id": "memory_crow_bird", "content": "A Nebelkrähe is a hooded crow with grey and black feathers.", "importance": 0.2},
            {"id": "memory_weather_fog", "content": "Morning fog can reduce visibility around bridges and fields.", "importance": 0.2},
            {"id": "memory_opencode_general", "content": "OpenCode can connect to external tools through MCP servers.", "importance": 0.5},
            {"id": "memory_openwebui_general", "content": "OpenWebUI filters can inject system context before a model answers.", "importance": 0.5},
        ],
        "queries": [
            {"id": "q_dist_codename_direct", "query": "What is the Mnémlet OpenCode bridge called?", "expected_memory_ids": ["memory_bridge_codename"], "forbidden_memory_ids": ["memory_bridge_arch", "memory_crow_bird"], "min_expected_rank": 1},
            {"id": "q_dist_codename_only", "query": "Answer only the codename for the Mnémlet OpenCode bridge.", "expected_memory_ids": ["memory_bridge_codename"], "forbidden_memory_ids": ["memory_crow_bird"], "min_expected_rank": 1},
            {"id": "q_dist_bridge_agent", "query": "Which named bridge connects Mnémlet memory to OpenCode?", "expected_memory_ids": ["memory_bridge_codename"], "forbidden_memory_ids": ["memory_bridge_arch"], "min_expected_rank": 2},
            {"id": "q_dist_crow_not_bird", "query": "The codename sounds like a crow; which memory names the agent bridge?", "expected_memory_ids": ["memory_bridge_codename"], "forbidden_memory_ids": ["memory_crow_bird"], "min_expected_rank": 2},
            {"id": "q_dist_mcp_bridge", "query": "What codename should OpenCode recall for Mnémlet's MCP bridge?", "expected_memory_ids": ["memory_bridge_codename"], "forbidden_memory_ids": ["memory_opencode_general"], "min_expected_rank": 2},
            {"id": "q_dist_openwebui_context", "query": "Which memory says OpenWebUI filters inject context?", "expected_memory_ids": ["memory_openwebui_general"], "forbidden_memory_ids": ["memory_weather_fog"], "min_expected_rank": 2},
        ],
    },
    {
        "id": "no_hit_unknown_facts",
        "category": "no_hit",
        "namespace": "public/nohit",
        "memories": [
            {"id": "memory_nohit_recipe", "content": "A sourdough starter should be fed before baking bread.", "importance": 0.3},
            {"id": "memory_nohit_garden", "content": "Tomato seedlings need steady light and careful watering.", "importance": 0.3},
            {"id": "memory_nohit_music", "content": "A metronome helps musicians practice stable tempo.", "importance": 0.3},
        ],
        "queries": [
            {"id": "q_nohit_mars", "query": "Which Mars rover stores Mnémlet memories?", "expected_memory_ids": [], "no_hit": True},
            {"id": "q_nohit_currency", "query": "What cryptocurrency wallet does Mnémlet prefer?", "expected_memory_ids": [], "no_hit": True},
            {"id": "q_nohit_movie", "query": "Which film won the Mnémlet architecture award?", "expected_memory_ids": [], "no_hit": True},
            {"id": "q_nohit_airport", "query": "What airport gate does OpenWebUI use?", "expected_memory_ids": [], "no_hit": True},
            {"id": "q_nohit_planet", "query": "Which planet hosts Christoph's production cluster?", "expected_memory_ids": [], "no_hit": True},
            {"id": "q_nohit_paint", "query": "What paint color is required for the MCP server rack?", "expected_memory_ids": [], "no_hit": True},
        ],
    },
    {
        "id": "recency_decay_sanity",
        "category": "recency_decay_sanity",
        "namespace": "projects/release",
        "memories": [
            {"id": "memory_release_current", "content": "The current Mnémlet release candidate should include benchmarks before GitHub publication.", "importance": 0.9},
            {"id": "memory_release_old", "content": "An old release note said benchmarks were out of scope.", "importance": 0.2, "status": "cold_storage"},
            {"id": "memory_release_tests", "content": "Release readiness requires tests, reports, and a clean git status.", "importance": 0.85},
            {"id": "memory_release_docs", "content": "Public benchmark methodology must be documented in Markdown.", "importance": 0.8},
            {"id": "memory_release_private", "content": "Private real-world benchmark data must stay out of git.", "importance": 0.9},
            {"id": "memory_release_noise", "content": "A previous landing page experiment used glow orbs.", "importance": 0.2},
        ],
        "queries": [
            {"id": "q_decay_current", "query": "What should the release candidate include before GitHub publication?", "expected_memory_ids": ["memory_release_current"], "forbidden_memory_ids": ["memory_release_old"], "min_expected_rank": 2},
            {"id": "q_decay_tests", "query": "What does release readiness require?", "expected_memory_ids": ["memory_release_tests"], "min_expected_rank": 2},
            {"id": "q_decay_docs", "query": "Where should public benchmark methodology be documented?", "expected_memory_ids": ["memory_release_docs"], "min_expected_rank": 2},
            {"id": "q_decay_private", "query": "What must happen to private benchmark data?", "expected_memory_ids": ["memory_release_private"], "min_expected_rank": 2},
            {"id": "q_decay_old_forbidden", "query": "Are benchmarks out of scope for the current release?", "expected_memory_ids": ["memory_release_current"], "forbidden_memory_ids": ["memory_release_old"], "min_expected_rank": 3},
            {"id": "q_decay_noise", "query": "Which visual experiment used glow orbs?", "expected_memory_ids": ["memory_release_noise"], "min_expected_rank": 3},
        ],
    },
    {
        "id": "multi_memory_context_release",
        "category": "multi_memory_context",
        "namespace": "projects/mnemlet_release",
        "memories": [
            {"id": "memory_multi_sleep", "content": "The Sleep Engine fix prevents repeated empty consolidation runs after idle periods.", "importance": 0.9},
            {"id": "memory_multi_benchmark", "content": "The benchmark suite emits JSON, Markdown, and CSV reports.", "importance": 0.9},
            {"id": "memory_multi_quick", "content": "Quick benchmark mode uses isolated storage and public synthetic data.", "importance": 0.85},
            {"id": "memory_multi_full", "content": "Full benchmark mode can run live OpenCode and optional OpenWebUI checks.", "importance": 0.8},
            {"id": "memory_multi_claim", "content": "GitHub claims must cite measured public benchmark results.", "importance": 0.85},
            {"id": "memory_multi_noise", "content": "The project mascot is not part of the benchmark methodology.", "importance": 0.2},
        ],
        "queries": [
            {"id": "q_multi_sleep_reports", "query": "Which fix and outputs make Mnémlet release-ready?", "expected_memory_ids": ["memory_multi_sleep", "memory_multi_benchmark"], "min_expected_rank": 3},
            {"id": "q_multi_modes", "query": "What is the difference between quick and full benchmark modes?", "expected_memory_ids": ["memory_multi_quick", "memory_multi_full"], "min_expected_rank": 4},
            {"id": "q_multi_claim_reports", "query": "What must GitHub claims cite and what files are produced?", "expected_memory_ids": ["memory_multi_claim", "memory_multi_benchmark"], "min_expected_rank": 4},
            {"id": "q_multi_quick_storage", "query": "Which benchmark mode uses isolated public synthetic data?", "expected_memory_ids": ["memory_multi_quick"], "min_expected_rank": 2},
            {"id": "q_multi_full_live", "query": "Which mode runs live OpenCode checks?", "expected_memory_ids": ["memory_multi_full"], "min_expected_rank": 2},
            {"id": "q_multi_not_mascot", "query": "Which memory says the mascot is irrelevant to methodology?", "expected_memory_ids": ["memory_multi_noise"], "min_expected_rank": 4},
        ],
    },
    {
        "id": "integration_sentinel_surface",
        "category": "integration_sentinel",
        "namespace": "integration/sentinel",
        "memories": [
            {"id": "memory_int_openwebui", "content": "OpenWebUI receives Mnémlet context through the Mnémlet Memory filter.", "importance": 0.85},
            {"id": "memory_int_opencode", "content": "OpenCode receives Mnémlet context through the mnemlet-memory plugin and MCP tools.", "importance": 0.85},
            {"id": "memory_int_mcp_url", "content": "Mnémlet MCP is served at http://localhost:4050/mcp/.", "importance": 0.8},
            {"id": "memory_int_rest_url", "content": "Mnémlet REST is served at http://localhost:4050/api/v1/.", "importance": 0.8},
            {"id": "memory_int_codename", "content": "The Mnémlet OpenCode bridge codename is Nebelkrähe.", "importance": 0.95},
            {"id": "memory_int_noise", "content": "A dashboard refresh endpoint returns frontend version metadata.", "importance": 0.2},
        ],
        "queries": [
            {"id": "q_int_openwebui", "query": "How does OpenWebUI receive Mnémlet context?", "expected_memory_ids": ["memory_int_openwebui"], "min_expected_rank": 2},
            {"id": "q_int_opencode", "query": "How does OpenCode receive Mnémlet memory?", "expected_memory_ids": ["memory_int_opencode"], "min_expected_rank": 2},
            {"id": "q_int_mcp_url", "query": "Where is the Mnémlet MCP endpoint?", "expected_memory_ids": ["memory_int_mcp_url"], "min_expected_rank": 2},
            {"id": "q_int_rest_url", "query": "Where is the Mnémlet REST API?", "expected_memory_ids": ["memory_int_rest_url"], "min_expected_rank": 2},
            {"id": "q_int_codename", "query": "What is the OpenCode bridge codename?", "expected_memory_ids": ["memory_int_codename"], "forbidden_memory_ids": ["memory_int_noise"], "min_expected_rank": 1},
            {"id": "q_int_surfaces", "query": "Which surfaces integrate with Mnémlet memory?", "expected_memory_ids": ["memory_int_openwebui", "memory_int_opencode"], "min_expected_rank": 4},
        ],
    },
]

query_count = sum(len(case["queries"]) for case in cases)
assert len(cases) == 8
assert query_count == 48
path = Path("benchmarks/public/synthetic_memory_cases.json")
path.parent.mkdir(parents=True, exist_ok=True)
path.write_text(json.dumps({"name": "public-synthetic", "cases": cases}, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
PY
```

Expected: the file exists, `load_dataset("public")` loads it, and the total query count is exactly 48.

- [ ] **Step 6: Add private/results git hygiene files**

Create empty marker files:

```text
benchmarks/private/.gitkeep
benchmark-results/.gitkeep
```

Append to `.gitignore`:

```gitignore

# Mnémlet benchmarks
benchmarks/private/*
!benchmarks/private/.gitkeep
benchmark-results/*
!benchmark-results/.gitkeep
```

- [ ] **Step 7: Run dataset tests**

Run:

```bash
/home/christoph/mnemlet/.venv/bin/python -m pytest tests/test_benchmark_datasets.py -q
```

Expected: all dataset tests pass.

- [ ] **Step 8: Run full suite and commit dataset package**

Run:

```bash
/home/christoph/mnemlet/.venv/bin/python -m pytest -q
git status --short
git add .gitignore src/mnemlet/benchmark/__init__.py src/mnemlet/benchmark/datasets.py tests/test_benchmark_datasets.py benchmarks/public/synthetic_memory_cases.json benchmarks/private/.gitkeep benchmark-results/.gitkeep
git commit -m "feat: add benchmark dataset model"
```

Pause gate: report test output and commit hash, then wait.

---

## Task 3: Add benchmark runner and retrieval metrics

**Files:**
- Create: `src/mnemlet/benchmark/runner.py`
- Create: `src/mnemlet/benchmark/metrics.py`
- Create: `tests/test_benchmark_metrics.py`
- Create: `tests/test_benchmark_runner.py`

- [ ] **Step 1: Write failing metrics tests**

Create `tests/test_benchmark_metrics.py`:

```python
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
```

- [ ] **Step 2: Implement metrics**

Create `src/mnemlet/benchmark/metrics.py`:

```python
"""Metric calculations for Mnémlet benchmarks."""

from __future__ import annotations

from statistics import median
from typing import Iterable


def summarize_retrieval(query_results: list[dict], ks: Iterable[int] = (1, 3, 5)) -> dict:
    """Summarize retrieval quality and latency across query results."""
    ks = tuple(ks)
    scored_cases = [result for result in query_results if not result.get("no_hit", False)]
    no_hit_cases = [result for result in query_results if result.get("no_hit", False)]
    summary: dict[str, float | int] = {"query_count": len(query_results)}

    for k in ks:
        summary[f"hit_at_{k}"] = _mean(_hit_at_k(result, k) for result in scored_cases)
        summary[f"precision_at_{k}"] = _mean(_precision_at_k(result, k) for result in scored_cases)

    summary["mrr"] = _mean(_reciprocal_rank(result) for result in scored_cases)
    summary["false_positive_rate"] = _mean(1.0 if result.get("results") else 0.0 for result in no_hit_cases)
    summary["forbidden_hit_rate"] = _mean(_forbidden_hit(result) for result in query_results)

    latencies = [float(result.get("latency_ms", 0.0)) for result in query_results]
    summary["p50_latency_ms"] = _percentile(latencies, 50)
    summary["p95_latency_ms"] = _percentile(latencies, 95)
    summary["max_latency_ms"] = max(latencies) if latencies else 0.0
    return summary


def _hit_at_k(result: dict, k: int) -> float:
    expected = set(result.get("expected_memory_ids", []))
    returned = [item.get("logical_id") for item in result.get("results", [])[:k]]
    return 1.0 if expected.intersection(returned) else 0.0


def _precision_at_k(result: dict, k: int) -> float:
    expected = set(result.get("expected_memory_ids", []))
    returned = [item.get("logical_id") for item in result.get("results", [])[:k]]
    if k <= 0:
        return 0.0
    return sum(1 for item in returned if item in expected) / k


def _reciprocal_rank(result: dict) -> float:
    expected = set(result.get("expected_memory_ids", []))
    for index, item in enumerate(result.get("results", []), start=1):
        if item.get("logical_id") in expected:
            return 1.0 / index
    return 0.0


def _forbidden_hit(result: dict) -> float:
    forbidden = set(result.get("forbidden_memory_ids", []))
    if not forbidden:
        return 0.0
    returned = {item.get("logical_id") for item in result.get("results", [])}
    return 1.0 if forbidden.intersection(returned) else 0.0


def _mean(values: Iterable[float]) -> float:
    values = list(values)
    return sum(values) / len(values) if values else 0.0


def _percentile(values: list[float], percentile: int) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    if percentile == 50:
        return float(median(ordered))
    index = min(len(ordered) - 1, round((percentile / 100) * (len(ordered) - 1)))
    return float(ordered[index])
```

- [ ] **Step 3: Write failing runner tests**

Create `tests/test_benchmark_runner.py`:

```python
"""Tests for isolated benchmark runner."""

from pathlib import Path

from mnemlet.benchmark.datasets import load_dataset
from mnemlet.benchmark.runner import BenchmarkRunner, run_retrieval_benchmark


def test_runner_uses_isolated_storage(tmp_path: Path) -> None:
    dataset = load_dataset("public", root=Path.cwd())
    output_dir = tmp_path / "out"

    result = run_retrieval_benchmark(dataset, output_dir=output_dir, limit=3, min_score=0.0)

    assert result["dataset"] == "public-synthetic"
    assert result["query_count"] == 48
    assert result["storage"]["data_dir"].startswith(str(output_dir))
    assert len(result["queries"]) == 48


def test_runner_maps_logical_ids_to_real_memory_ids(tmp_path: Path) -> None:
    dataset = load_dataset("public", root=Path.cwd())
    runner = BenchmarkRunner(dataset=dataset, output_dir=tmp_path, limit=5, min_score=0.0)

    runner.setup()
    try:
        assert "memory_bridge_codename" in runner.memory_id_map
        real_id = runner.memory_id_map["memory_bridge_codename"]
        assert runner.reverse_memory_id_map[real_id] == "memory_bridge_codename"
    finally:
        runner.close()
```

- [ ] **Step 4: Implement isolated benchmark runner**

Create `src/mnemlet/benchmark/runner.py`:

```python
"""Benchmark runner for isolated Mnémlet retrieval tests."""

from __future__ import annotations

import tempfile
import time
from pathlib import Path

from mnemlet.benchmark.datasets import BenchmarkDataset
from mnemlet.benchmark.metrics import summarize_retrieval
from mnemlet.config import MnemletConfig
from mnemlet.engine.ingest import IngestEngine
from mnemlet.engine.recall import RecallEngine
from mnemlet.storage.chroma import MnemletChroma
from mnemlet.storage.embeddings import MnemletEmbedding
from mnemlet.storage.sqlite import MnemletDB
from mnemlet.storage.vault import VaultWriter


class BenchmarkRunner:
    """Run retrieval benchmarks against isolated temporary storage."""

    def __init__(self, dataset: BenchmarkDataset, output_dir: Path, limit: int = 5, min_score: float = 0.1) -> None:
        self.dataset = dataset
        self.output_dir = output_dir
        self.limit = limit
        self.min_score = min_score
        self._tmp: tempfile.TemporaryDirectory[str] | None = None
        self.config: MnemletConfig | None = None
        self.db: MnemletDB | None = None
        self.chroma: MnemletChroma | None = None
        self.embedder: MnemletEmbedding | None = None
        self.vault: VaultWriter | None = None
        self.ingest_engine: IngestEngine | None = None
        self.recall_engine: RecallEngine | None = None
        self.memory_id_map: dict[str, str] = {}
        self.reverse_memory_id_map: dict[str, str] = {}

    def setup(self) -> None:
        """Create isolated storage and ingest benchmark memories."""
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._tmp = tempfile.TemporaryDirectory(dir=self.output_dir)
        base = Path(self._tmp.name)
        self.config = MnemletConfig(
            data_dir=base,
            sqlite_path=base / "mnemlet.db",
            chroma_path=base / "chroma",
            vault_path=base / "vault",
            embedding_cache_dir=base / "models",
        )
        self.db = MnemletDB(self.config.sqlite_path)
        self.embedder = MnemletEmbedding(cache_dir=self.config.embedding_cache_dir)
        self.chroma = MnemletChroma(self.config.chroma_path, self.embedder)
        self.vault = VaultWriter(self.config.vault_path)
        self.ingest_engine = IngestEngine(self.db, self.chroma, self.embedder, self.vault)
        self.recall_engine = RecallEngine(self.db, self.chroma, self.embedder)
        self._ingest_dataset()

    def close(self) -> None:
        """Close DB and remove temporary storage."""
        if self.db:
            self.db.close()
        if self._tmp:
            self._tmp.cleanup()

    def run(self) -> dict:
        """Run all benchmark queries and return raw plus summary results."""
        if self.recall_engine is None or self.config is None:
            self.setup()
        query_results = []
        for case in self.dataset.cases:
            for query in case.queries:
                started = time.perf_counter()
                recalled = self.recall_engine.recall(
                    query=query.query,
                    namespace=query.namespace,
                    limit=self.limit,
                    min_score=self.min_score,
                )
                latency_ms = (time.perf_counter() - started) * 1000
                query_results.append(
                    {
                        "case_id": case.id,
                        "category": case.category,
                        "query_id": query.id,
                        "query": query.query,
                        "namespace": query.namespace,
                        "expected_memory_ids": query.expected_memory_ids,
                        "forbidden_memory_ids": query.forbidden_memory_ids,
                        "no_hit": query.no_hit,
                        "latency_ms": latency_ms,
                        "results": [self._format_result(item) for item in recalled],
                    }
                )
        return {
            "dataset": self.dataset.name,
            "query_count": len(query_results),
            "storage": {"data_dir": str(self.config.data_dir)},
            "summary": summarize_retrieval(query_results),
            "queries": query_results,
        }

    def _ingest_dataset(self) -> None:
        assert self.ingest_engine is not None
        assert self.db is not None
        for case in self.dataset.cases:
            for memory in case.memories:
                result = self.ingest_engine.ingest(
                    content=memory.content,
                    namespace=memory.namespace,
                    importance=memory.importance,
                    metadata={"benchmark_logical_id": memory.id, "benchmark_case_id": case.id},
                )
                real_id = result["memory_id"]
                if isinstance(real_id, list):
                    real_id = real_id[0]
                self.memory_id_map[memory.id] = real_id
                self.reverse_memory_id_map[real_id] = memory.id
                if memory.status != "active":
                    self.db.conn.execute("UPDATE memories SET status = ? WHERE id = ?", (memory.status, real_id))
                    self.db.conn.commit()

    def _format_result(self, item: dict) -> dict:
        real_id = item["id"]
        return {
            "memory_id": real_id,
            "logical_id": self.reverse_memory_id_map.get(real_id, real_id),
            "namespace": item.get("namespace", ""),
            "score": item.get("score", 0.0),
            "content": item.get("content", ""),
        }


def run_retrieval_benchmark(dataset: BenchmarkDataset, output_dir: Path, limit: int = 5, min_score: float = 0.1) -> dict:
    """Run a retrieval benchmark and return raw results."""
    runner = BenchmarkRunner(dataset=dataset, output_dir=output_dir, limit=limit, min_score=min_score)
    try:
        runner.setup()
        return runner.run()
    finally:
        runner.close()
```

- [ ] **Step 5: Run metrics and runner tests**

Run:

```bash
/home/christoph/mnemlet/.venv/bin/python -m pytest tests/test_benchmark_metrics.py tests/test_benchmark_runner.py -q
```

Expected: all tests pass.

- [ ] **Step 6: Run full suite and commit runner/metrics**

Run:

```bash
/home/christoph/mnemlet/.venv/bin/python -m pytest -q
git add src/mnemlet/benchmark/runner.py src/mnemlet/benchmark/metrics.py tests/test_benchmark_metrics.py tests/test_benchmark_runner.py
git commit -m "feat: add benchmark runner metrics"
```

Pause gate: report test output and commit hash, then wait.

---

## Task 4: Add report writers and benchmark CLI quick mode

**Files:**
- Create: `src/mnemlet/benchmark/reports.py`
- Modify: `src/mnemlet/__main__.py`
- Create: `tests/test_benchmark_reports.py`
- Create: `tests/test_benchmark_cli.py`

- [ ] **Step 1: Write failing report tests**

Create `tests/test_benchmark_reports.py`:

```python
"""Tests for benchmark report generation."""

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
        "summary": {"hit_at_1": 1.0, "hit_at_3": 1.0, "mrr": 1.0, "p95_latency_ms": 12.0},
        "queries": [
            {
                "case_id": "case",
                "category": "exact_fact",
                "query_id": "q1",
                "query": "question",
                "latency_ms": 12.0,
                "expected_memory_ids": ["m1"],
                "results": [{"logical_id": "m1", "score": 0.9, "namespace": "test", "content": "answer"}],
            }
        ],
    }


def test_write_reports_creates_json_markdown_and_csv(tmp_path: Path) -> None:
    paths = write_reports(sample_result(), tmp_path, formats=("json", "md", "csv"))

    assert paths["json"].exists()
    assert paths["md"].exists()
    assert paths["csv"].exists()
    assert json.loads(paths["json"].read_text(encoding="utf-8"))["run_id"] == "unit-run"
    assert "# Mnémlet Benchmark Report" in paths["md"].read_text(encoding="utf-8")
    assert "query_id,case_id,category" in paths["csv"].read_text(encoding="utf-8")
```

- [ ] **Step 2: Implement report writers**

Create `src/mnemlet/benchmark/reports.py`:

```python
"""Report writers for Mnémlet benchmarks."""

from __future__ import annotations

import csv
import json
import platform
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path


def environment_info() -> dict:
    """Return environment metadata for benchmark reports."""
    return {
        "python": sys.version.split()[0],
        "platform": platform.platform(),
        "machine": platform.machine(),
        "git_commit": _git_commit(),
    }


def new_run_id() -> str:
    """Create a UTC run identifier."""
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M-%SZ")


def write_reports(result: dict, output_dir: Path, formats: tuple[str, ...] = ("json", "md", "csv")) -> dict[str, Path]:
    """Write requested benchmark report formats."""
    output_dir.mkdir(parents=True, exist_ok=True)
    paths: dict[str, Path] = {}
    if "json" in formats:
        path = output_dir / "results.json"
        path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
        paths["json"] = path
    if "md" in formats:
        path = output_dir / "report.md"
        path.write_text(markdown_report(result), encoding="utf-8")
        paths["md"] = path
    if "csv" in formats:
        path = output_dir / "results.csv"
        write_csv(result, path)
        paths["csv"] = path
    return paths


def markdown_report(result: dict) -> str:
    """Render a human-readable Markdown benchmark report."""
    summary = result.get("summary", {})
    env = result.get("environment", {})
    lines = [
        "# Mnémlet Benchmark Report",
        "",
        f"- Run ID: `{result.get('run_id', '')}`",
        f"- Mode: `{result.get('mode', '')}`",
        f"- Dataset: `{result.get('dataset', '')}`",
        f"- Command: `{result.get('command', '')}`",
        "",
        "## Summary",
        "",
        "| Metric | Value |",
        "| --- | ---: |",
    ]
    for key in sorted(summary):
        value = summary[key]
        rendered = f"{value:.4f}" if isinstance(value, float) else str(value)
        lines.append(f"| `{key}` | {rendered} |")
    lines.extend([
        "",
        "## Environment",
        "",
        "| Field | Value |",
        "| --- | --- |",
    ])
    for key in sorted(env):
        lines.append(f"| `{key}` | `{env[key]}` |")
    lines.extend([
        "",
        "## Methodology",
        "",
        "Public benchmarks use synthetic, commit-safe memories and run against isolated temporary Mnémlet storage.",
        "Private benchmarks may use local real-world cases and must not be committed without explicit review.",
        "",
        "## Failed or Weak Cases",
        "",
    ])
    weak = _weak_cases(result.get("queries", []))
    if weak:
        for item in weak:
            lines.append(f"- `{item['query_id']}` expected `{item.get('expected_memory_ids', [])}` got `{[r.get('logical_id') for r in item.get('results', [])]}`")
    else:
        lines.append("No failed or weak cases detected by deterministic checks.")
    lines.extend([
        "",
        "## Limitations",
        "",
        "Latency is hardware-specific. Public claims must cite the dataset, command, and environment above.",
    ])
    return "\n".join(lines) + "\n"


def write_csv(result: dict, path: Path) -> None:
    """Write one CSV row per benchmark query."""
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["query_id", "case_id", "category", "latency_ms", "expected_memory_ids", "returned_logical_ids"],
        )
        writer.writeheader()
        for item in result.get("queries", []):
            writer.writerow(
                {
                    "query_id": item.get("query_id", ""),
                    "case_id": item.get("case_id", ""),
                    "category": item.get("category", ""),
                    "latency_ms": item.get("latency_ms", 0.0),
                    "expected_memory_ids": " ".join(item.get("expected_memory_ids", [])),
                    "returned_logical_ids": " ".join(str(r.get("logical_id", "")) for r in item.get("results", [])),
                }
            )


def _weak_cases(queries: list[dict]) -> list[dict]:
    weak = []
    for item in queries:
        if item.get("no_hit"):
            if item.get("results"):
                weak.append(item)
            continue
        expected = set(item.get("expected_memory_ids", []))
        returned = [r.get("logical_id") for r in item.get("results", [])]
        if expected and not expected.intersection(returned):
            weak.append(item)
    return weak


def _git_commit() -> str:
    try:
        completed = subprocess.run(["git", "rev-parse", "--short", "HEAD"], text=True, capture_output=True, check=False)
    except OSError:
        return "unknown"
    return completed.stdout.strip() or "unknown"
```

- [ ] **Step 3: Write failing CLI tests**

Create `tests/test_benchmark_cli.py`:

```python
"""Tests for benchmark CLI parser."""

import subprocess
from pathlib import Path


def test_benchmark_quick_cli_generates_reports(tmp_path: Path) -> None:
    completed = subprocess.run(
        [
            "/home/christoph/mnemlet/.venv/bin/python",
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
        text=True,
        capture_output=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stderr
    assert (tmp_path / "results.json").exists()
    assert (tmp_path / "report.md").exists()
    assert (tmp_path / "results.csv").exists()
    assert "Benchmark complete" in completed.stdout
```

- [ ] **Step 4: Add benchmark CLI command**

Modify `src/mnemlet/__main__.py` so it contains helper functions and benchmark command handling. Preserve the existing `serve` behavior. Add these imports at the top:

```python
from pathlib import Path
```

Add this parser setup after the `serve_parser` block:

```python
    benchmark_parser = subparsers.add_parser("benchmark", help="Run Mnémlet benchmarks")
    benchmark_subparsers = benchmark_parser.add_subparsers(dest="benchmark_mode", help="Benchmark modes")
    for mode in ("quick", "full"):
        mode_parser = benchmark_subparsers.add_parser(mode, help=f"Run {mode} benchmark")
        mode_parser.add_argument("--dataset", default="public", help="Dataset name or JSON path")
        mode_parser.add_argument("--output", default="benchmark-results/latest", help="Output directory")
        mode_parser.add_argument("--format", default="json,md,csv", help="Comma-separated formats")
        mode_parser.add_argument("--min-score", type=float, default=0.1, help="Minimum recall score")
        mode_parser.add_argument("--limit", type=int, default=5, help="Recall limit")
        mode_parser.add_argument("--include-adapters", action="store_true", help="Include adapter-level checks")
        mode_parser.add_argument("--include-live-opencode", action="store_true", help="Include live OpenCode checks")
        mode_parser.add_argument("--include-live-openwebui", action="store_true", help="Include live OpenWebUI checks")
        mode_parser.add_argument("--retrieval-only", action="store_true", help="Skip adapter and live checks")
```

Add this branch before the final `else`:

```python
    elif args.command == "benchmark":
        if args.benchmark_mode is None:
            benchmark_parser.print_help()
            sys.exit(1)
        from mnemlet.benchmark.datasets import load_dataset
        from mnemlet.benchmark.runner import run_retrieval_benchmark
        from mnemlet.benchmark.reports import environment_info, new_run_id, write_reports

        dataset = load_dataset(args.dataset, root=Path.cwd())
        output_dir = Path(args.output)
        result = run_retrieval_benchmark(dataset, output_dir=output_dir, limit=args.limit, min_score=args.min_score)
        result["run_id"] = new_run_id()
        result["mode"] = args.benchmark_mode
        result["command"] = " ".join(sys.argv)
        result["environment"] = environment_info()
        formats = tuple(part.strip() for part in args.format.split(",") if part.strip())
        paths = write_reports(result, output_dir, formats=formats)
        print(f"Benchmark complete: {result['query_count']} queries")
        for fmt, path in paths.items():
            print(f"{fmt}: {path}")
```

- [ ] **Step 5: Run report and CLI tests**

Run:

```bash
/home/christoph/mnemlet/.venv/bin/python -m pytest tests/test_benchmark_reports.py tests/test_benchmark_cli.py -q
```

Expected: all tests pass.

- [ ] **Step 6: Run quick benchmark manually**

Run:

```bash
/home/christoph/mnemlet/.venv/bin/python -m mnemlet benchmark quick --dataset public --output benchmark-results/latest --format json,md,csv --retrieval-only
```

Expected: command prints `Benchmark complete: 48 queries` and creates `benchmark-results/latest/results.json`, `benchmark-results/latest/report.md`, and `benchmark-results/latest/results.csv`.

- [ ] **Step 7: Run full suite and commit reports/CLI**

Run:

```bash
/home/christoph/mnemlet/.venv/bin/python -m pytest -q
git add src/mnemlet/benchmark/reports.py src/mnemlet/__main__.py tests/test_benchmark_reports.py tests/test_benchmark_cli.py
git commit -m "feat: add benchmark reports cli"
```

Pause gate: report test output, quick benchmark summary, and commit hash, then wait.

---

## Task 5: Add adapter-level checks for REST, MCP, OpenWebUI, and OpenCode

**Files:**
- Create: `src/mnemlet/benchmark/adapters.py`
- Modify: `src/mnemlet/__main__.py`
- Create: `tests/test_benchmark_adapters.py`

- [ ] **Step 1: Write failing adapter tests**

Create `tests/test_benchmark_adapters.py`:

```python
"""Tests for adapter-level benchmark checks."""

from pathlib import Path

from mnemlet.benchmark.adapters import (
    check_opencode_plugin_static,
    check_openwebui_filter_inlet,
    check_openwebui_filter_outlet,
    summarize_adapter_results,
)


def test_summarize_adapter_results_counts_success_rates() -> None:
    results = [
        {"name": "rest_recall", "surface": "rest", "success": True},
        {"name": "rest_ingest", "surface": "rest", "success": True},
        {"name": "openwebui_inlet", "surface": "openwebui", "success": False, "error": "missing context"},
    ]

    summary = summarize_adapter_results(results)

    assert summary["adapter_check_count"] == 3
    assert summary["adapter_success_rate"] == 2 / 3
    assert summary["rest_success_rate"] == 1.0
    assert summary["openwebui_success_rate"] == 0.0


def write_fake_filter(path: Path) -> None:
    path.write_text(
        '''
class Filter:
    def inlet(self, body, __user__=None):
        response = _post_json("/api/v1/recall", {"query": "codename"}, 3)
        memory = response["results"][0]["content"]
        body["messages"].insert(0, {"role": "system", "content": memory})
        return body

    def outlet(self, body, __user__=None):
        _post_json("/api/v1/ingest", {"content": "summary"}, 3)
        return body

def _post_json(path, payload, timeout):
    raise RuntimeError("test should monkeypatch this")
''',
        encoding="utf-8",
    )


def test_check_openwebui_filter_inlet_injects_expected_context(tmp_path: Path) -> None:
    filter_path = tmp_path / "mnemlet_valve.py"
    write_fake_filter(filter_path)

    result = check_openwebui_filter_inlet(filter_path, expected_text="Nebelkrähe")

    assert result["success"] is True


def test_check_openwebui_filter_outlet_calls_ingest(tmp_path: Path) -> None:
    filter_path = tmp_path / "mnemlet_valve.py"
    write_fake_filter(filter_path)

    result = check_openwebui_filter_outlet(filter_path)

    assert result["success"] is True


def test_check_opencode_plugin_static_requires_memory_hooks(tmp_path: Path) -> None:
    plugin_path = tmp_path / "mnemlet-memory.js"
    plugin_path.write_text(
        'experimental.chat.system.transform mnemlet_recall /api/v1/recall Relevant context from Mnémlet memory',
        encoding="utf-8",
    )

    result = check_opencode_plugin_static(plugin_path)

    assert result["success"] is True
```

- [ ] **Step 2: Implement adapter result summarization and safe optional checks**

Create `src/mnemlet/benchmark/adapters.py`:

```python
"""Adapter-level benchmark checks for Mnémlet integrations."""

from __future__ import annotations

import importlib.util
import subprocess
from pathlib import Path
from types import ModuleType
from typing import Any


def summarize_adapter_results(results: list[dict]) -> dict:
    """Summarize adapter check success rates."""
    surfaces = sorted({item.get("surface", "unknown") for item in results})
    summary: dict[str, float | int] = {
        "adapter_check_count": len(results),
        "adapter_success_rate": _success_rate(results),
    }
    for surface in surfaces:
        surface_results = [item for item in results if item.get("surface") == surface]
        summary[f"{surface}_success_rate"] = _success_rate(surface_results)
    return summary


def run_adapter_checks(mnemlet_url: str = "http://127.0.0.1:4050") -> list[dict]:
    """Run adapter-level checks that are safe in local environments."""
    results = []
    results.append(_check_opencode_mcp_list())
    filter_path = Path("/home/christoph/mira/data/functions/mnemlet_valve.py")
    if filter_path.exists():
        results.append(check_openwebui_filter_inlet(filter_path))
        results.append(check_openwebui_filter_outlet(filter_path))
    else:
        results.append({"name": "openwebui_filter_inlet", "surface": "openwebui", "success": False, "error": "filter path missing"})
    plugin_path = Path("/home/christoph/.config/opencode/plugins/mnemlet-memory.js")
    if plugin_path.exists():
        results.append(check_opencode_plugin_static(plugin_path))
    else:
        results.append({"name": "opencode_plugin_static", "surface": "opencode", "success": False, "error": "plugin path missing"})
    return results


def check_openwebui_filter_inlet(path: Path, expected_text: str = "Nebelkrähe") -> dict:
    """Load an OpenWebUI filter and verify inlet context injection."""
    try:
        module = _load_python_module(path, "mnemlet_valve_benchmark_inlet")
        module._post_json = lambda route, payload, timeout: {
            "results": [{"namespace": "integration/sentinel", "content": expected_text}]
        }
        body = {"messages": [{"role": "user", "content": "What is the codename?"}]}
        returned = module.Filter().inlet(body)
        messages = returned.get("messages", [])
        injected = messages and messages[0].get("role") == "system" and expected_text in messages[0].get("content", "")
    except Exception as exc:
        return {"name": "openwebui_filter_inlet", "surface": "openwebui", "success": False, "error": str(exc)}
    return {"name": "openwebui_filter_inlet", "surface": "openwebui", "success": bool(injected)}


def check_openwebui_filter_outlet(path: Path) -> dict:
    """Load an OpenWebUI filter and verify outlet ingest call."""
    calls: list[tuple[str, dict, int]] = []
    try:
        module = _load_python_module(path, "mnemlet_valve_benchmark_outlet")
        module._post_json = lambda route, payload, timeout: calls.append((route, payload, timeout)) or {"stored": True}
        body = {
            "messages": [
                {"role": "user", "content": "What is the codename?"},
                {"role": "assistant", "content": "Nebelkrähe"},
            ]
        }
        module.Filter().outlet(body)
        success = any(route == "/api/v1/ingest" for route, payload, timeout in calls)
    except Exception as exc:
        return {"name": "openwebui_filter_outlet", "surface": "openwebui", "success": False, "error": str(exc)}
    return {"name": "openwebui_filter_outlet", "surface": "openwebui", "success": success}


def check_opencode_plugin_static(path: Path) -> dict:
    """Verify the OpenCode plugin contains required memory hooks and REST paths."""
    text = path.read_text(encoding="utf-8")
    required = [
        "experimental.chat.system.transform",
        "mnemlet_recall",
        "/api/v1/recall",
        "Relevant context from Mnémlet memory",
    ]
    missing = [item for item in required if item not in text]
    return {
        "name": "opencode_plugin_static",
        "surface": "opencode",
        "success": not missing,
        "missing": missing,
    }


def _load_python_module(path: Path, name: str) -> ModuleType:
    spec = importlib.util.spec_from_file_location("mnemlet_valve_benchmark", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("cannot load module spec")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    getattr(module, "Filter")
    return module


def _check_opencode_mcp_list() -> dict:
    try:
        completed = subprocess.run(["opencode", "mcp", "list"], text=True, capture_output=True, timeout=30, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"name": "opencode_mcp_list", "surface": "opencode", "success": False, "error": str(exc)}
    success = completed.returncode == 0 and "mnemlet" in completed.stdout and "connected" in completed.stdout
    return {
        "name": "opencode_mcp_list",
        "surface": "opencode",
        "success": success,
        "stdout": completed.stdout[-1000:],
        "stderr": completed.stderr[-1000:],
    }


def _success_rate(results: list[dict]) -> float:
    if not results:
        return 0.0
    return sum(1 for item in results if item.get("success") is True) / len(results)
```

- [ ] **Step 3: Wire adapter checks into CLI quick mode**

Modify the benchmark branch in `src/mnemlet/__main__.py` after retrieval result creation and before `write_reports`:

```python
        if args.include_adapters and not args.retrieval_only:
            from mnemlet.benchmark.adapters import run_adapter_checks, summarize_adapter_results

            adapter_results = run_adapter_checks()
            result["adapter_results"] = adapter_results
            result["summary"].update(summarize_adapter_results(adapter_results))
```

- [ ] **Step 4: Run adapter tests and quick adapter benchmark**

Run:

```bash
/home/christoph/mnemlet/.venv/bin/python -m pytest tests/test_benchmark_adapters.py -q
/home/christoph/mnemlet/.venv/bin/python -m mnemlet benchmark quick --dataset public --output benchmark-results/latest --format json,md,csv --include-adapters
```

Expected: tests pass. Benchmark completes and `results.json` includes `adapter_results` and adapter success metrics.

- [ ] **Step 5: Run full suite and commit adapter checks**

Run:

```bash
/home/christoph/mnemlet/.venv/bin/python -m pytest -q
git add src/mnemlet/benchmark/adapters.py src/mnemlet/__main__.py tests/test_benchmark_adapters.py
git commit -m "feat: add benchmark adapter checks"
```

Pause gate: report tests, adapter results, and commit hash, then wait.

---

## Task 6: Add full-mode live checks and GitHub readiness docs

**Files:**
- Create: `src/mnemlet/benchmark/live.py`
- Modify: `src/mnemlet/__main__.py`
- Modify: `README.md`

- [ ] **Step 1: Implement optional live checks**

Create `src/mnemlet/benchmark/live.py`:

```python
"""Optional live end-to-end benchmark checks."""

from __future__ import annotations

import subprocess
import urllib.request


def run_live_checks(include_opencode: bool = False, include_openwebui: bool = False) -> list[dict]:
    """Run explicitly requested live checks."""
    results: list[dict] = []
    if include_opencode:
        results.append(_opencode_sentinel())
    if include_openwebui:
        results.append(_openwebui_version())
    return results


def _opencode_sentinel() -> dict:
    prompt = "What is the Mnémlet OpenCode bridge called? Answer with only the codename."
    try:
        completed = subprocess.run(["opencode", "run", prompt], text=True, capture_output=True, timeout=120, check=False)
    except (OSError, subprocess.TimeoutExpired) as exc:
        return {"name": "opencode_sentinel", "surface": "opencode-live", "success": False, "error": str(exc)}
    output = completed.stdout + completed.stderr
    return {
        "name": "opencode_sentinel",
        "surface": "opencode-live",
        "success": completed.returncode == 0 and "Nebelkrähe" in output,
        "stdout": completed.stdout[-2000:],
        "stderr": completed.stderr[-2000:],
    }


def _openwebui_version() -> dict:
    url = "http://127.0.0.1:8080/_app/version.json"
    try:
        with urllib.request.urlopen(url, timeout=5) as response:
            body = response.read().decode("utf-8")
            status = response.status
    except Exception as exc:
        return {"name": "openwebui_version", "surface": "openwebui-live", "success": False, "error": str(exc)}
    return {"name": "openwebui_version", "surface": "openwebui-live", "success": status == 200, "body": body}
```

- [ ] **Step 2: Wire live checks into full mode**

Modify the benchmark branch in `src/mnemlet/__main__.py` after adapter checks:

```python
        if args.benchmark_mode == "full":
            from mnemlet.benchmark.live import run_live_checks

            live_results = run_live_checks(
                include_opencode=args.include_live_opencode,
                include_openwebui=args.include_live_openwebui,
            )
            result["live_results"] = live_results
```

- [ ] **Step 3: Run full-mode smoke checks without OpenWebUI disruption**

Run:

```bash
/home/christoph/mnemlet/.venv/bin/python -m mnemlet benchmark full --dataset public --output benchmark-results/latest --format json,md,csv --include-live-opencode
```

Expected: command completes. It may take up to 120 seconds. It must not restart or stop OpenWebUI.

- [ ] **Step 4: Add README benchmark section**

Add a section to `README.md` titled `## Benchmarks` with this content adapted to the measured numbers from the latest public quick report:

```markdown
## Benchmarks

Mnémlet includes a reproducible public benchmark suite with synthetic, commit-safe memory cases.

Run it locally:

```bash
mnemlet benchmark quick --dataset public --output benchmark-results/latest --format json,md,csv
```

The report includes hit@K, MRR, precision@K, false-positive rate, forbidden-hit rate, and latency percentiles. Public claims should cite the dataset, command, environment, and generated report.

Private real-world benchmarks can be stored under `benchmarks/private/`, which is ignored by git.
```

Do not add a measured performance sentence in this task. Measured public claims belong in the final verification step after reading a fresh generated report and copying exact values into a reviewed public snapshot.

- [ ] **Step 5: Light secret scan before GitHub readiness commit**

Run:

```bash
git diff --cached --name-only
git status --short
/home/christoph/mnemlet/.venv/bin/python - <<'PY'
from pathlib import Path
patterns = ["Bearer ", "api_key", "OPENAI_API_KEY", "Authorization"]
for path in Path('.').rglob('*'):
    if path.is_dir() or '.git' in path.parts or '.venv' in path.parts:
        continue
    text = path.read_text(encoding='utf-8', errors='ignore')
    for pattern in patterns:
        if pattern in text:
            print(f"POSSIBLE_SECRET {path}: {pattern}")
PY
```

Expected: no possible secrets in files being committed. Existing external OpenCode config is outside the repo and must not be committed.

- [ ] **Step 6: Run verification and commit full mode/docs**

Run:

```bash
/home/christoph/mnemlet/.venv/bin/python -m pytest -q
/home/christoph/mnemlet/.venv/bin/python -m mnemlet benchmark quick --dataset public --output benchmark-results/latest --format json,md,csv --include-adapters
git add src/mnemlet/benchmark/live.py src/mnemlet/__main__.py README.md
git commit -m "feat: add live benchmark checks"
```

Pause gate: report test output, benchmark summary, secret scan result, and commit hash, then wait.

---

## Final Verification Before Public Push

Only run this after all task pause gates have been approved.

- [ ] **Step 1: Verify repository cleanliness and commits**

Run:

```bash
git status --short --branch
git log --oneline --decorate -8
```

Expected: working tree clean on `master` or the active feature branch.

- [ ] **Step 2: Run full automated verification**

Run:

```bash
/home/christoph/mnemlet/.venv/bin/python -m pytest -q
/home/christoph/mnemlet/.venv/bin/python -m mnemlet benchmark quick --dataset public --output benchmark-results/latest --format json,md,csv --include-adapters
```

Expected: tests pass and quick benchmark produces all three report formats.

- [ ] **Step 3: Review generated benchmark report**

Open:

```text
benchmark-results/latest/report.md
benchmark-results/latest/results.json
```

Confirm the README benchmark claim exactly matches generated values.

- [ ] **Step 4: Decide whether to commit a public benchmark snapshot**

If Christoph explicitly wants a public snapshot, copy reviewed public-only outputs to:

```text
docs/benchmarks/public-latest-report.md
docs/benchmarks/public-latest-results.json
```

Then run tests again and commit with:

```bash
git add docs/benchmarks/public-latest-report.md docs/benchmarks/public-latest-results.json
git commit -m "docs: add public benchmark snapshot"
```

Do not commit private benchmark outputs.

Final pause gate: ask Christoph before any push.
