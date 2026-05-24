# Mnémlet Memory Intelligence Core v0.2 Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build the v0.2 Quality Spine MVP: status-aware recall, Context Packs, Abstention, Supersession, minimal Provenance, Review Commands, OpenWebUI/OpenCode contracts, and a deterministic Quality Benchmark.

**Architecture:** Add a focused `mnemlet.intelligence` layer while keeping existing v0.1 ingest/recall/MCP/REST contracts compatible. The existing `RecallEngine` becomes status- and provenance-aware; new intelligent behavior is exposed through additive REST/MCP routes. OpenWebUI and OpenCode remain legacy-compatible while tests lock down abstention/no-injection behavior before any adapter switch.

**Tech Stack:** Python 3.12, pytest, FastAPI, Pydantic, SQLite, ChromaDB, dataclasses, argparse, pathlib, local fakes for OpenWebUI/OpenCode, local Ollama detector only behind injected testable interfaces.

---

## Required Pause Gates

After each task below:

1. Run the task's verification commands.
2. Report exact command output and exit status.
3. Commit only if Christoph has explicitly allowed commits for this execution run; otherwise leave changes staged/unstaged and report the exact diff state.
4. Stop and wait for Christoph to say `Weiter`, `Go`, or an equivalent continuation.

Do not push to GitHub from this plan. Do not restart, kill, or migrate OpenWebUI.

## File Structure

### Existing files to modify

- Modify: `src/mnemlet/storage/sqlite.py`
  - Responsibility: additive intelligence schema migration, status/type/metadata update helpers, interaction queries.
- Modify: `src/mnemlet/constants.py`
  - Responsibility: intelligence thresholds, memory statuses, memory types, confirm boost.
- Modify: `src/mnemlet/engine/recall.py`
  - Responsibility: status-aware filtering, source/rank provenance, Context Pack input.
- Modify: `src/mnemlet/engine/ingest.py`
  - Responsibility: optional dedup bypass, explicit memory type updates, injected Supersession pipeline.
- Modify: `src/mnemlet/server/app.py`
  - Responsibility: wire new routes and intelligence services.
- Modify: `src/mnemlet/server/mcp_server.py`
  - Responsibility: expose `mnemlet_context`, `mnemlet_explain`, `mnemlet_remember`, `mnemlet_forget`, `mnemlet_replace`, `mnemlet_confirm`.
- Modify: `src/mnemlet/server/routes/__init__.py`
  - Responsibility: keep route package importable; no code change is required while `app.py` imports route modules directly.
- Modify: `src/mnemlet/benchmark/adapters.py`
  - Responsibility: safe adapter contract checks for abstention/no-injection and Context Pack compatibility.
- Modify: `src/mnemlet/benchmark/datasets.py`
  - Responsibility: Quality Benchmark dataclasses and JSON validation beside existing retrieval dataset model.
- Modify: `src/mnemlet/benchmark/reports.py`
  - Responsibility: quality-specific report sections and CSV rows without breaking retrieval reports.
- Modify: `src/mnemlet/__main__.py`
  - Responsibility: add `mnemlet benchmark quality` CLI mode.

### New source files

- Create: `src/mnemlet/intelligence/__init__.py`
  - Responsibility: package exports.
- Create: `src/mnemlet/intelligence/classifier.py`
  - Responsibility: deterministic memory type classification.
- Create: `src/mnemlet/intelligence/policy.py`
  - Responsibility: fixed MVP lifecycle policies and status filters.
- Create: `src/mnemlet/intelligence/abstention.py`
  - Responsibility: no-hit/low-confidence/all-filtered/contradictory abstention decisions.
- Create: `src/mnemlet/intelligence/context_pack.py`
  - Responsibility: primary/supporting/superseded grouping and pack metadata.
- Create: `src/mnemlet/intelligence/provenance.py`
  - Responsibility: explain payload assembly.
- Create: `src/mnemlet/intelligence/review.py`
  - Responsibility: remember/forget/replace/confirm operations over existing engines/storage.
- Create: `src/mnemlet/intelligence/supersession.py`
  - Responsibility: injected contradiction detector protocol, fake-testable auto-supersession pipeline, LLM adapter.
- Create: `src/mnemlet/server/routes/context.py`
  - Responsibility: `POST /api/v1/context`.
- Create: `src/mnemlet/server/routes/explain.py`
  - Responsibility: `GET /api/v1/explain/{memory_id}`.
- Create: `src/mnemlet/server/routes/review.py`
  - Responsibility: remember/forget/replace/confirm REST routes.
- Create: `src/mnemlet/benchmark/quality.py`
  - Responsibility: isolated Quality Benchmark runner and metrics.

### New benchmark data and tests

- Create: `benchmarks/public/synthetic_quality_scenarios.json`
  - Responsibility: commit-safe synthetic Quality MVP scenarios.
- Create: `tests/test_intelligence_storage.py`
  - Responsibility: schema migration and storage helper tests.
- Create: `tests/test_intelligence_classifier_policy.py`
  - Responsibility: classifier and fixed policy tests.
- Create: `tests/test_intelligence_context_pack.py`
  - Responsibility: Context Pack and Abstention unit tests.
- Create: `tests/test_intelligence_review.py`
  - Responsibility: remember/forget/replace/confirm unit tests.
- Create: `tests/test_intelligence_supersession.py`
  - Responsibility: auto-supersession with fake detector.
- Create: `tests/test_context_api.py`
  - Responsibility: REST context/explain/review route tests.
- Create: `tests/test_openwebui_filter.py`
  - Responsibility: OpenWebUI filter contract tests with monkeypatched REST calls.
- Modify: `tests/test_recall.py`
  - Responsibility: status filtering and provenance in legacy recall.
- Modify: `tests/test_api.py`
  - Responsibility: legacy API compatibility assertions.
- Existing: `tests/test_mcp.py`
  - Responsibility: unchanged regression suite run after MCP tools are added.
- Modify: `tests/test_benchmark_adapters.py`
  - Responsibility: adapter abstention/no-injection checks.
- Create: `tests/test_quality_benchmark.py`
  - Responsibility: Quality scenario loading, runner, metrics.
- Modify: `tests/test_benchmark_cli.py`
  - Responsibility: `mnemlet benchmark quality` smoke test.

---

## Task 1: Add intelligence schema and storage helpers

**Files:**
- Create: `tests/test_intelligence_storage.py`
- Modify: `src/mnemlet/storage/sqlite.py`
- Modify: `src/mnemlet/constants.py`

- [ ] **Step 1: Write failing storage schema tests**

Create `tests/test_intelligence_storage.py` with this content:

```python
"""Tests for intelligence schema migrations and storage helpers."""

import sqlite3
from pathlib import Path

from mnemlet.storage.sqlite import MnemletDB


INTELLIGENCE_COLUMNS = {
    "memory_type",
    "type_confidence",
    "type_source",
    "superseded_by",
    "content_summary",
}


def test_new_database_has_intelligence_columns(tmp_path: Path) -> None:
    db = MnemletDB(tmp_path / "mnemlet.db")
    try:
        columns = {row[1] for row in db.conn.execute("PRAGMA table_info(memories)").fetchall()}
    finally:
        db.close()

    assert INTELLIGENCE_COLUMNS.issubset(columns)


def test_existing_database_is_migrated_idempotently(tmp_path: Path) -> None:
    db_path = tmp_path / "old.db"
    conn = sqlite3.connect(db_path)
    conn.execute(
        """CREATE TABLE memories (
            id TEXT PRIMARY KEY,
            namespace TEXT NOT NULL,
            content_hash TEXT NOT NULL DEFAULT '',
            content_preview TEXT NOT NULL,
            chunk_count INTEGER DEFAULT 1,
            retention_score REAL DEFAULT 0.5,
            importance REAL DEFAULT 0.5,
            created_at TEXT NOT NULL,
            last_accessed_at TEXT NOT NULL,
            access_count INTEGER DEFAULT 0,
            metadata_json TEXT DEFAULT '{}',
            status TEXT DEFAULT 'active'
        )"""
    )
    conn.commit()
    conn.close()

    db = MnemletDB(db_path)
    db.close()
    db = MnemletDB(db_path)
    try:
        columns = {row[1] for row in db.conn.execute("PRAGMA table_info(memories)").fetchall()}
    finally:
        db.close()

    assert INTELLIGENCE_COLUMNS.issubset(columns)


def test_memory_status_type_and_metadata_helpers(tmp_path: Path) -> None:
    db = MnemletDB(tmp_path / "mnemlet.db")
    try:
        memory = db.insert_memory(content_preview="The service runs on port 4050", namespace="infra")

        db.update_memory_type(memory["id"], "fact", 0.8, "heuristic", "Service port")
        db.update_memory_metadata(memory["id"], {"supersedes": "old-id", "policy_flags": ["checked"]})
        db.update_memory_status(memory["id"], "superseded", superseded_by="new-id")
        updated = db.get_memory(memory["id"])
    finally:
        db.close()

    assert updated is not None
    assert updated["memory_type"] == "fact"
    assert updated["type_confidence"] == 0.8
    assert updated["type_source"] == "heuristic"
    assert updated["content_summary"] == "Service port"
    assert updated["status"] == "superseded"
    assert updated["superseded_by"] == "new-id"
    assert '"supersedes": "old-id"' in updated["metadata_json"]
    assert '"policy_flags": ["checked"]' in updated["metadata_json"]
```

- [ ] **Step 2: Run the failing tests**

Run: `pytest tests/test_intelligence_storage.py -v`

Expected: FAIL because the intelligence columns and helper methods do not exist yet.

- [ ] **Step 3: Add constants**

Append this to `src/mnemlet/constants.py`:

```python

# Intelligence memory types
MEMORY_TYPE_FACT = "fact"
MEMORY_TYPE_PREFERENCE = "preference"
MEMORY_TYPE_INSTRUCTION = "instruction"
MEMORY_TYPE_EVENT = "event"
MEMORY_TYPE_CONTEXT = "context"
MEMORY_TYPES = (
    MEMORY_TYPE_FACT,
    MEMORY_TYPE_PREFERENCE,
    MEMORY_TYPE_INSTRUCTION,
    MEMORY_TYPE_EVENT,
    MEMORY_TYPE_CONTEXT,
)

# Intelligence memory statuses
MEMORY_STATUS_ACTIVE = "active"
MEMORY_STATUS_COLD_STORAGE = "cold_storage"
MEMORY_STATUS_DELETED = "deleted"
MEMORY_STATUS_SUPERSEDED = "superseded"
MEMORY_STATUS_FORGOTTEN = "forgotten"
MEMORY_STATUSES = (
    MEMORY_STATUS_ACTIVE,
    MEMORY_STATUS_COLD_STORAGE,
    MEMORY_STATUS_DELETED,
    MEMORY_STATUS_SUPERSEDED,
    MEMORY_STATUS_FORGOTTEN,
)

# Context Pack thresholds
CONTEXT_PRIMARY_SCORE_THRESHOLD = 0.70
CONTEXT_SUPPORTING_SCORE_THRESHOLD = 0.30
CONTRADICTION_AUTO_SUPERSEDE_THRESHOLD = 0.80

# Review commands
BOOST_CONFIRM = 0.20
```

- [ ] **Step 4: Implement SQLite migration and helper methods**

Modify `src/mnemlet/storage/sqlite.py`:

1. Add imports at the top:

```python
import json
from typing import Any, Optional

from mnemlet.constants import MEMORY_STATUSES
```

Keep the existing `sqlite3`, `uuid`, `datetime`, `Path` imports. Remove the old `from typing import Optional` line after adding the combined import.

2. Add this constant after `SCHEMA`:

```python
INTELLIGENCE_MEMORY_COLUMNS: dict[str, str] = {
    "memory_type": "TEXT DEFAULT NULL",
    "type_confidence": "REAL DEFAULT NULL",
    "type_source": "TEXT DEFAULT NULL",
    "superseded_by": "TEXT DEFAULT NULL",
    "content_summary": "TEXT DEFAULT NULL",
}
```

3. In `MnemletDB.__init__`, after `self.conn.executescript(SCHEMA)`, add:

```python
        self._ensure_intelligence_schema()
```

4. Add these methods to `MnemletDB` after `_list_tables`:

```python
    def _table_columns(self, table_name: str) -> set[str]:
        """Return column names for a SQLite table."""
        rows = self.conn.execute(f"PRAGMA table_info({table_name})").fetchall()
        return {str(row[1]) for row in rows}

    def _ensure_intelligence_schema(self) -> None:
        """Add v0.2 intelligence columns to existing databases idempotently."""
        columns = self._table_columns("memories")
        for column_name, column_sql in INTELLIGENCE_MEMORY_COLUMNS.items():
            if column_name not in columns:
                self.conn.execute(
                    f"ALTER TABLE memories ADD COLUMN {column_name} {column_sql}"
                )
        self.conn.commit()
```

5. Remove the local `import json` inside `insert_memory` because `json` is now imported at module level.

6. Add these methods after `get_memory`:

```python
    def update_memory_status(
        self,
        memory_id: str,
        status: str,
        superseded_by: str | None = None,
    ) -> dict | None:
        """Update a memory status and optional supersession link."""
        if status not in MEMORY_STATUSES:
            raise ValueError(f"invalid memory status: {status}")
        self.conn.execute(
            "UPDATE memories SET status = ?, superseded_by = COALESCE(?, superseded_by) WHERE id = ?",
            (status, superseded_by, memory_id),
        )
        self.conn.commit()
        return self.get_memory(memory_id)

    def update_memory_type(
        self,
        memory_id: str,
        memory_type: str,
        confidence: float,
        source: str,
        summary: str | None = None,
    ) -> dict | None:
        """Update memory type metadata."""
        bounded_confidence = max(0.0, min(1.0, confidence))
        self.conn.execute(
            """UPDATE memories
               SET memory_type = ?, type_confidence = ?, type_source = ?, content_summary = ?
               WHERE id = ?""",
            (memory_type, bounded_confidence, source, summary, memory_id),
        )
        self.conn.commit()
        return self.get_memory(memory_id)

    def update_memory_metadata(self, memory_id: str, updates: dict[str, Any]) -> dict | None:
        """Merge updates into a memory's metadata_json object."""
        memory = self.get_memory(memory_id)
        if memory is None:
            return None
        try:
            metadata = json.loads(memory.get("metadata_json") or "{}")
        except json.JSONDecodeError:
            metadata = {}
        metadata.update(updates)
        self.conn.execute(
            "UPDATE memories SET metadata_json = ? WHERE id = ?",
            (json.dumps(metadata, ensure_ascii=False), memory_id),
        )
        self.conn.commit()
        return self.get_memory(memory_id)
```

- [ ] **Step 5: Run storage tests**

Run: `pytest tests/test_intelligence_storage.py -v`

Expected: PASS.

- [ ] **Step 6: Run SQLite regression tests**

Run: `pytest tests/test_sqlite.py tests/test_intelligence_storage.py -v`

Expected: PASS.

- [ ] **Step 7: Commit Task 1 changes if commits are authorized**

Run:

```bash
git add src/mnemlet/constants.py src/mnemlet/storage/sqlite.py tests/test_intelligence_storage.py
git commit -m "feat: add intelligence memory schema"
```

Expected: commit succeeds if Christoph authorized commits. If commits are not authorized, do not run these commands; report `git status --short`.

---

## Task 2: Make legacy recall status-aware and provenance-aware

**Files:**
- Modify: `tests/test_recall.py`
- Modify: `src/mnemlet/engine/recall.py`
- Modify: `src/mnemlet/storage/sqlite.py`

- [ ] **Step 1: Add failing recall tests**

Append these tests to `tests/test_recall.py`:

```python

def test_recall_excludes_superseded_memories_by_default(embedder):
    """Legacy recall must not return superseded memories as active facts."""
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        db = MnemletDB(base / "test.db")
        chroma = MnemletChroma(base / "chroma", embedder)
        ingest = IngestEngine(db=db, chroma=chroma, embedder=embedder)
        recall = RecallEngine(db=db, chroma=chroma, embedder=embedder)

        old = ingest.ingest("The service runs on port 8080", namespace="infra")
        ingest.ingest("The service runs on port 9090", namespace="infra")
        db.update_memory_status(str(old["memory_id"]), "superseded")

        results = recall.recall("What port does the service run on?", namespace="infra", limit=5)

        assert all(item["id"] != old["memory_id"] for item in results)
        assert all(item["status"] == "active" for item in results)


def test_recall_includes_minimal_provenance(embedder):
    """Legacy recall results expose additive provenance without breaking content/score."""
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        db = MnemletDB(base / "test.db")
        chroma = MnemletChroma(base / "chroma", embedder)
        ingest = IngestEngine(db=db, chroma=chroma, embedder=embedder)
        recall = RecallEngine(db=db, chroma=chroma, embedder=embedder)

        ingest.ingest("Christoph prefers self-hosted tools", namespace="preferences")

        results = recall.recall("self hosted tools", namespace="preferences", limit=5)

        assert results
        first = results[0]
        assert first["content"]
        assert first["score"] >= 0
        assert first["namespace"] == "preferences"
        assert first["source"] in {"vector", "fts", "hybrid"}
        assert first["rank"] == 1
        assert first["status"] == "active"
        assert "created_at" in first
        assert "access_count" in first
```

- [ ] **Step 2: Run the failing recall tests**

Run: `pytest tests/test_recall.py::test_recall_excludes_superseded_memories_by_default tests/test_recall.py::test_recall_includes_minimal_provenance -v`

Expected: FAIL because recall returns Chroma hits without SQLite status/provenance.

- [ ] **Step 3: Add active-status helper to SQLite**

Add this method to `MnemletDB` after `get_memory` in `src/mnemlet/storage/sqlite.py`:

```python
    def get_memories_by_ids(self, memory_ids: list[str]) -> dict[str, dict]:
        """Return memories keyed by ID for the provided IDs."""
        if not memory_ids:
            return {}
        bind_marks = ",".join("?" for _ in memory_ids)
        rows = self.conn.execute(
            f"SELECT * FROM memories WHERE id IN ({bind_marks})",
            tuple(memory_ids),
        ).fetchall()
        return {str(row["id"]): dict(row) for row in rows}
```

- [ ] **Step 4: Update RecallEngine to preserve source and attach provenance**

Modify `src/mnemlet/engine/recall.py`:

1. Change imports:

```python
from typing import Optional

from mnemlet.constants import (
    DEFAULT_TOP_N,
    HYBRID_BM25_WEIGHT,
    HYBRID_VECTOR_WEIGHT,
    MAX_RECALL_TOKENS,
    MAX_TOP_N,
    MEMORY_STATUS_ACTIVE,
)
from mnemlet.engine.decay import DecayEngine
```

2. Change the `recall` signature:

```python
    def recall(
        self,
        query: str,
        namespace: Optional[str] = None,
        limit: int = DEFAULT_TOP_N,
        min_score: float = 0.0,
        include_statuses: set[str] | None = None,
    ) -> list[dict]:
```

3. Replace the merge/filter block inside `recall` with:

```python
        merged = self._merge_results(vector_results, fts_results, limit * 2)
        enriched = self._attach_memory_rows(merged, include_statuses or {MEMORY_STATUS_ACTIVE})
        filtered = [m for m in enriched if m["score"] >= min_score]
        for index, item in enumerate(filtered, start=1):
            item["rank"] = index
```

Leave the token budget and interaction loop after this block, but make sure the function still returns `filtered[:limit]`.

4. Replace `_merge_results` with:

```python
    def _merge_results(self, vector: list[dict], fts: list[dict], limit: int) -> list[dict]:
        """Merge vector and FTS results, weighted, deduplicated, and source-aware."""
        scored: dict[str, dict] = {}

        for item in vector:
            sid = item["id"]
            scored[sid] = scored.get(
                sid,
                {
                    "id": sid,
                    "content": item["content"],
                    "namespace": item["namespace"],
                    "score": 0.0,
                    "source": "vector",
                    "vector_seen": False,
                    "fts_seen": False,
                },
            )
            scored[sid]["score"] += HYBRID_VECTOR_WEIGHT * item["score"]
            scored[sid]["vector_seen"] = True
            scored[sid]["content"] = item["content"] or scored[sid]["content"]

        for item in fts:
            sid = item["id"]
            scored[sid] = scored.get(
                sid,
                {
                    "id": sid,
                    "content": item["content"],
                    "namespace": item["namespace"],
                    "score": 0.0,
                    "source": "fts",
                    "vector_seen": False,
                    "fts_seen": False,
                },
            )
            scored[sid]["score"] += HYBRID_BM25_WEIGHT * item["score"]
            scored[sid]["fts_seen"] = True
            if not scored[sid].get("content"):
                scored[sid]["content"] = item["content"]

        for item in scored.values():
            vector_seen = bool(item.pop("vector_seen"))
            fts_seen = bool(item.pop("fts_seen"))
            if vector_seen and fts_seen:
                item["source"] = "hybrid"
            elif item.get("source") not in {"vector", "fts"}:
                item["source"] = "vector"

        return sorted(scored.values(), key=lambda x: x["score"], reverse=True)[:limit]
```

5. Add this method after `_merge_results`:

```python
    def _attach_memory_rows(self, items: list[dict], include_statuses: set[str]) -> list[dict]:
        """Attach SQLite memory metadata and filter by status."""
        memory_rows = self.db.get_memories_by_ids([str(item["id"]) for item in items])
        enriched: list[dict] = []
        for item in items:
            memory = memory_rows.get(str(item["id"]))
            if memory is None:
                continue
            status = str(memory.get("status", "active"))
            if status not in include_statuses:
                continue
            merged = dict(item)
            merged.update(
                {
                    "namespace": memory.get("namespace", item.get("namespace", "")),
                    "status": status,
                    "created_at": memory.get("created_at"),
                    "access_count": memory.get("access_count", 0),
                    "memory_type": memory.get("memory_type"),
                    "type_confidence": memory.get("type_confidence"),
                    "type_source": memory.get("type_source"),
                    "superseded_by": memory.get("superseded_by"),
                    "metadata_json": memory.get("metadata_json", "{}"),
                }
            )
            enriched.append(merged)
        return enriched
```

- [ ] **Step 5: Run recall tests**

Run: `pytest tests/test_recall.py -v`

Expected: PASS.

- [ ] **Step 6: Run API compatibility tests**

Run: `pytest tests/test_api.py tests/test_benchmark_runner.py -v`

Expected: PASS. The additive recall fields must not break existing callers.

- [ ] **Step 7: Commit Task 2 changes if commits are authorized**

Run:

```bash
git add src/mnemlet/storage/sqlite.py src/mnemlet/engine/recall.py tests/test_recall.py
git commit -m "feat: add status-aware recall provenance"
```

Expected: commit succeeds if Christoph authorized commits. If not authorized, report `git status --short`.

---

## Task 3: Add deterministic Classifier and MVP Policy

**Files:**
- Create: `src/mnemlet/intelligence/__init__.py`
- Create: `src/mnemlet/intelligence/classifier.py`
- Create: `src/mnemlet/intelligence/policy.py`
- Create: `tests/test_intelligence_classifier_policy.py`
- Modify: `src/mnemlet/engine/ingest.py`
- Modify: `tests/test_ingest.py`

- [ ] **Step 1: Write failing classifier/policy tests**

Create `tests/test_intelligence_classifier_policy.py` with this content:

```python
"""Tests for deterministic memory classification and MVP lifecycle policies."""

from mnemlet.intelligence.classifier import classify_memory
from mnemlet.intelligence.policy import can_auto_supersede, recall_statuses


def test_classifier_detects_preferences() -> None:
    result = classify_memory("Christoph bevorzugt Self-Hosting für AI tools", "prefs")

    assert result.memory_type == "preference"
    assert result.source == "heuristic"
    assert 0.7 <= result.confidence <= 0.8


def test_classifier_detects_instructions_before_preferences() -> None:
    result = classify_memory("OpenWebUI darf nicht restarted werden", "ops")

    assert result.memory_type == "instruction"
    assert result.summary == "OpenWebUI darf nicht restarted werden"


def test_classifier_defaults_to_context() -> None:
    result = classify_memory("Repo liegt unter /home/christoph/mnemlet", "project")

    assert result.memory_type == "context"
    assert result.confidence == 0.5


def test_policy_allows_safe_supersession_types() -> None:
    assert can_auto_supersede("fact") is True
    assert can_auto_supersede("preference") is True
    assert can_auto_supersede("context") is True


def test_policy_protects_instructions_events_and_unknown_types() -> None:
    assert can_auto_supersede("instruction") is False
    assert can_auto_supersede("event") is False
    assert can_auto_supersede(None) is False


def test_recall_statuses_default_to_active_only() -> None:
    assert recall_statuses(include_superseded=False) == {"active"}
    assert recall_statuses(include_superseded=True) == {"active", "superseded"}
```

- [ ] **Step 2: Run the failing tests**

Run: `pytest tests/test_intelligence_classifier_policy.py -v`

Expected: FAIL because the `mnemlet.intelligence` package does not exist yet.

- [ ] **Step 3: Create intelligence package exports**

Create `src/mnemlet/intelligence/__init__.py` with this content:

```python
"""Memory Intelligence Core helpers for Mnémlet v0.2."""
```

- [ ] **Step 4: Implement classifier**

Create `src/mnemlet/intelligence/classifier.py` with this content:

```python
"""Deterministic memory type classifier for the v0.2 MVP."""

from __future__ import annotations

import re
from dataclasses import dataclass

from mnemlet.constants import (
    MEMORY_TYPE_CONTEXT,
    MEMORY_TYPE_EVENT,
    MEMORY_TYPE_FACT,
    MEMORY_TYPE_INSTRUCTION,
    MEMORY_TYPE_PREFERENCE,
)


@dataclass(frozen=True)
class ClassificationResult:
    """Result of classifying a memory."""

    memory_type: str
    confidence: float
    source: str
    summary: str


def classify_memory(content: str, namespace: str = "default") -> ClassificationResult:
    """Classify memory content into one fixed MVP memory type."""
    normalized = content.casefold()
    summary = _summary(content)
    if _contains_any(normalized, ("immer", "niemals", "muss", "darf nicht", "never", "always")):
        return ClassificationResult(MEMORY_TYPE_INSTRUCTION, 0.8, "heuristic", summary)
    if _contains_any(normalized, ("bevorzugt", "bevorzuge", "prefers", "prefer ", "mag lieber")):
        return ClassificationResult(MEMORY_TYPE_PREFERENCE, 0.75, "heuristic", summary)
    if _looks_like_event(content):
        return ClassificationResult(MEMORY_TYPE_EVENT, 0.7, "heuristic", summary)
    if _looks_like_fact(normalized):
        return ClassificationResult(MEMORY_TYPE_FACT, 0.6, "heuristic", summary)
    return ClassificationResult(MEMORY_TYPE_CONTEXT, 0.5, "heuristic", summary)


def _contains_any(text: str, needles: tuple[str, ...]) -> bool:
    return any(needle in text for needle in needles)


def _looks_like_event(content: str) -> bool:
    return bool(
        re.search(r"\b\d{4}-\d{2}-\d{2}\b", content)
        or re.search(r"\b\d{1,2}\.\s*[A-ZÄÖÜa-zäöü]+\b", content)
        or re.search(r"\b(am|um|deployment|termin|meeting)\b", content.casefold())
    )


def _looks_like_fact(text: str) -> bool:
    return _contains_any(text, (" ist ", " läuft ", " nutzt ", " uses ", " runs ", " is "))


def _summary(content: str, max_chars: int = 160) -> str:
    compact = " ".join(content.split())
    if len(compact) <= max_chars:
        return compact
    return compact[: max_chars - 1].rstrip() + "…"
```

- [ ] **Step 5: Implement policy**

Create `src/mnemlet/intelligence/policy.py` with this content:

```python
"""Fixed MVP lifecycle policies for Memory Intelligence Core v0.2."""

from __future__ import annotations

from mnemlet.constants import (
    MEMORY_STATUS_ACTIVE,
    MEMORY_STATUS_SUPERSEDED,
    MEMORY_TYPE_CONTEXT,
    MEMORY_TYPE_FACT,
    MEMORY_TYPE_PREFERENCE,
)

AUTO_SUPERSEDE_TYPES = {
    MEMORY_TYPE_FACT,
    MEMORY_TYPE_PREFERENCE,
    MEMORY_TYPE_CONTEXT,
}


def can_auto_supersede(memory_type: str | None) -> bool:
    """Return whether a memory type may be automatically superseded."""
    return memory_type in AUTO_SUPERSEDE_TYPES


def recall_statuses(include_superseded: bool = False) -> set[str]:
    """Return statuses eligible for recall/context assembly."""
    if include_superseded:
        return {MEMORY_STATUS_ACTIVE, MEMORY_STATUS_SUPERSEDED}
    return {MEMORY_STATUS_ACTIVE}
```

- [ ] **Step 6: Run classifier/policy tests**

Run: `pytest tests/test_intelligence_classifier_policy.py -v`

Expected: PASS.

- [ ] **Step 7: Add failing ingest classification test**

Append this test to `tests/test_ingest.py`:

```python

def test_ingest_classifies_memory_heuristically(engine):
    """New memories receive a deterministic MVP memory type."""
    result = engine.ingest(
        content="Christoph bevorzugt Self-Hosting für Agent Memory",
        namespace="preferences",
        importance=0.8,
    )

    memory = engine.db.get_memory(result["memory_id"])

    assert memory["memory_type"] == "preference"
    assert memory["type_source"] == "heuristic"
    assert memory["type_confidence"] >= 0.7
```

- [ ] **Step 8: Run failing ingest classification test**

Run: `pytest tests/test_ingest.py::test_ingest_classifies_memory_heuristically -v`

Expected: FAIL because `IngestEngine` does not call the classifier yet.

- [ ] **Step 9: Integrate classifier into IngestEngine**

Modify `src/mnemlet/engine/ingest.py`:

1. Add this import:

```python
from mnemlet.intelligence.classifier import classify_memory
```

2. After `db_result = self.db.insert_memory(...)`, add:

```python
            classification = classify_memory(chunk, namespace)
            self.db.update_memory_type(
                memory_id,
                classification.memory_type,
                classification.confidence,
                classification.source,
                classification.summary,
            )
            db_result = self.db.get_memory(memory_id) or db_result
```

- [ ] **Step 10: Run ingest/classifier tests**

Run: `pytest tests/test_ingest.py tests/test_intelligence_classifier_policy.py -v`

Expected: PASS.

- [ ] **Step 11: Commit Task 3 changes if commits are authorized**

Run:

```bash
git add src/mnemlet/intelligence src/mnemlet/engine/ingest.py tests/test_ingest.py tests/test_intelligence_classifier_policy.py
git commit -m "feat: add memory classifier policies"
```

Expected: commit succeeds if Christoph authorized commits. If not authorized, report `git status --short`.

---

## Task 4: Add Context Pack and Abstention core

**Files:**
- Create: `src/mnemlet/intelligence/abstention.py`
- Create: `src/mnemlet/intelligence/context_pack.py`
- Create: `tests/test_intelligence_context_pack.py`

- [ ] **Step 1: Write failing Context Pack tests**

Create `tests/test_intelligence_context_pack.py` with this content:

```python
"""Tests for Context Pack building and Abstention decisions."""

from mnemlet.intelligence.context_pack import build_context_pack


def test_context_pack_groups_primary_supporting_and_superseded() -> None:
    results = [
        {"id": "a", "content": "primary", "score": 0.8, "status": "active", "source": "vector", "rank": 1, "namespace": "n", "created_at": "now"},
        {"id": "b", "content": "supporting", "score": 0.4, "status": "active", "source": "fts", "rank": 2, "namespace": "n", "created_at": "now"},
        {"id": "c", "content": "weak", "score": 0.2, "status": "active", "source": "fts", "rank": 3, "namespace": "n", "created_at": "now"},
        {"id": "d", "content": "old", "score": 0.9, "status": "superseded", "source": "hybrid", "rank": 4, "namespace": "n", "created_at": "now"},
    ]

    pack = build_context_pack("query", results, include_superseded=True)

    assert [item["id"] for item in pack["context_pack"]["primary"]] == ["a"]
    assert [item["id"] for item in pack["context_pack"]["supporting"]] == ["b"]
    assert [item["id"] for item in pack["context_pack"]["superseded"]] == ["d"]
    assert pack["abstention"] is None
    assert pack["meta"]["pack_size"] == 3


def test_context_pack_abstains_on_no_results() -> None:
    pack = build_context_pack("unknown", [])

    assert pack["context_pack"] == {"primary": [], "supporting": [], "superseded": []}
    assert pack["abstention"]["reason"] == "no_relevant_memories"
    assert pack["meta"]["confidence"] == 0.0


def test_context_pack_abstains_on_low_confidence() -> None:
    results = [
        {"id": "weak", "content": "weak", "score": 0.2, "status": "active", "source": "vector", "rank": 1, "namespace": "n", "created_at": "now"}
    ]

    pack = build_context_pack("unknown", results)

    assert pack["context_pack"]["primary"] == []
    assert pack["context_pack"]["supporting"] == []
    assert pack["abstention"]["reason"] == "low_confidence_matches"


def test_context_pack_flags_contradictory_results() -> None:
    results = [
        {
            "id": "a",
            "content": "active contradiction",
            "score": 0.8,
            "status": "active",
            "source": "vector",
            "rank": 1,
            "namespace": "n",
            "created_at": "now",
            "policy_flags": ["contradiction_unresolved"],
        }
    ]

    pack = build_context_pack("query", results)

    assert pack["abstention"]["reason"] == "contradictory_results"
    assert "contradiction_unresolved" in pack["meta"]["policy_flags"]
```

- [ ] **Step 2: Run the failing Context Pack tests**

Run: `pytest tests/test_intelligence_context_pack.py -v`

Expected: FAIL because the modules do not exist.

- [ ] **Step 3: Implement Abstention helper**

Create `src/mnemlet/intelligence/abstention.py` with this content:

```python
"""Abstention decisions for Memory Intelligence Core v0.2."""

from __future__ import annotations

from mnemlet.constants import CONTEXT_SUPPORTING_SCORE_THRESHOLD


def abstention(reason: str) -> dict[str, str]:
    """Return a stable abstention payload for a reason."""
    suggestions = {
        "no_relevant_memories": "Store or confirm a relevant memory before relying on recall.",
        "low_confidence_matches": "Rephrase the query or store a more specific memory.",
        "all_results_filtered": "Only non-active memories matched this query.",
        "contradictory_results": "Resolve or explain contradictory memories before relying on this context.",
    }
    return {"reason": reason, "suggestion": suggestions[reason]}


def decide_abstention(candidates: list[dict], pack_items: list[dict], policy_flags: list[str]) -> dict[str, str] | None:
    """Return abstention payload when recall results are missing, weak, filtered, or contradictory."""
    if not candidates:
        return abstention("no_relevant_memories")
    highest = max(float(item.get("score", 0.0)) for item in candidates)
    if highest < CONTEXT_SUPPORTING_SCORE_THRESHOLD:
        return abstention("low_confidence_matches")
    if not pack_items:
        return abstention("all_results_filtered")
    if "contradiction_unresolved" in policy_flags:
        return abstention("contradictory_results")
    return None
```

- [ ] **Step 4: Implement Context Pack builder**

Create `src/mnemlet/intelligence/context_pack.py` with this content:

```python
"""Context Pack assembly for agent-friendly memory recall."""

from __future__ import annotations

import json
from typing import Any

from mnemlet.constants import (
    CONTEXT_PRIMARY_SCORE_THRESHOLD,
    CONTEXT_SUPPORTING_SCORE_THRESHOLD,
    MEMORY_STATUS_ACTIVE,
    MEMORY_STATUS_SUPERSEDED,
)
from mnemlet.intelligence.abstention import decide_abstention


def build_context_pack(
    query: str,
    results: list[dict[str, Any]],
    include_superseded: bool = False,
) -> dict[str, Any]:
    """Build a Context Pack from provenance-aware recall results."""
    primary: list[dict[str, Any]] = []
    supporting: list[dict[str, Any]] = []
    superseded: list[dict[str, Any]] = []
    policy_flags = _collect_policy_flags(results)

    for item in results:
        score = float(item.get("score", 0.0))
        status = str(item.get("status", MEMORY_STATUS_ACTIVE))
        packed = _pack_item(item)
        if status == MEMORY_STATUS_SUPERSEDED:
            if include_superseded:
                superseded.append(packed)
            continue
        if status != MEMORY_STATUS_ACTIVE:
            continue
        if score >= CONTEXT_PRIMARY_SCORE_THRESHOLD:
            primary.append(packed)
        elif score >= CONTEXT_SUPPORTING_SCORE_THRESHOLD:
            supporting.append(packed)

    pack_items = primary + supporting + superseded
    abstain = decide_abstention(results, primary + supporting, policy_flags)
    confidence = max((float(item.get("score", 0.0)) for item in primary + supporting), default=0.0)
    return {
        "query": query,
        "context_pack": {
            "primary": primary,
            "supporting": supporting,
            "superseded": superseded,
        },
        "abstention": abstain,
        "meta": {
            "total_candidates": len(results),
            "pack_size": len(pack_items),
            "confidence": confidence,
            "policy_flags": policy_flags,
        },
    }


def _pack_item(item: dict[str, Any]) -> dict[str, Any]:
    return {
        "id": item.get("id"),
        "content": item.get("content", ""),
        "score": item.get("score", 0.0),
        "namespace": item.get("namespace", ""),
        "memory_type": item.get("memory_type"),
        "status": item.get("status", MEMORY_STATUS_ACTIVE),
        "provenance": {
            "source": item.get("source", "unknown"),
            "rank": item.get("rank"),
            "created_at": item.get("created_at"),
            "access_count": item.get("access_count", 0),
            "policy_flags": _item_policy_flags(item),
        },
    }


def _collect_policy_flags(results: list[dict[str, Any]]) -> list[str]:
    flags: list[str] = []
    for item in results:
        for flag in _item_policy_flags(item):
            if flag not in flags:
                flags.append(flag)
    return flags


def _item_policy_flags(item: dict[str, Any]) -> list[str]:
    direct = item.get("policy_flags")
    if isinstance(direct, list):
        return [str(flag) for flag in direct]
    raw_metadata = item.get("metadata_json")
    if not isinstance(raw_metadata, str):
        return []
    try:
        metadata = json.loads(raw_metadata or "{}")
    except json.JSONDecodeError:
        return []
    flags = metadata.get("policy_flags", [])
    if not isinstance(flags, list):
        return []
    return [str(flag) for flag in flags]
```

- [ ] **Step 5: Run Context Pack tests**

Run: `pytest tests/test_intelligence_context_pack.py -v`

Expected: PASS.

- [ ] **Step 6: Commit Task 4 changes if commits are authorized**

Run:

```bash
git add src/mnemlet/intelligence/abstention.py src/mnemlet/intelligence/context_pack.py tests/test_intelligence_context_pack.py
git commit -m "feat: build context packs with abstention"
```

Expected: commit succeeds if Christoph authorized commits. If not authorized, report `git status --short`.

---

## Task 5: Expose Context Pack through REST and MCP

**Files:**
- Create: `src/mnemlet/server/routes/context.py`
- Modify: `src/mnemlet/server/app.py`
- Modify: `src/mnemlet/server/mcp_server.py`
- Create: `tests/test_context_api.py`

- [ ] **Step 1: Write failing context API test**

Create `tests/test_context_api.py` with this content:

```python
"""Tests for Context Pack REST API."""

import tempfile
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from mnemlet.config import MnemletConfig
from mnemlet.server.app import create_app


@asynccontextmanager
async def _client() -> AsyncIterator[AsyncClient]:
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        config = MnemletConfig(
            data_dir=base,
            sqlite_path=base / "mnemlet.db",
            chroma_path=base / "chroma",
            embedding_cache_dir=base / "models",
        )
        app = create_app(config)
        async with app.router.lifespan_context(app):
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as ac:
                yield ac


@pytest.mark.asyncio
async def test_context_endpoint_returns_context_pack() -> None:
    async with _client() as client:
        await client.post(
            "/api/v1/ingest",
            json={"content": "Christoph prefers self-hosted tools", "namespace": "prefs", "importance": 0.9},
        )

        resp = await client.post(
            "/api/v1/context",
            json={"query": "self hosted tools", "namespace": "prefs", "limit": 5},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["query"] == "self hosted tools"
    assert set(data["context_pack"]) == {"primary", "supporting", "superseded"}
    assert data["meta"]["total_candidates"] >= 1


@pytest.mark.asyncio
async def test_context_endpoint_abstains_without_results() -> None:
    async with _client() as client:
        resp = await client.post(
            "/api/v1/context",
            json={"query": "unknown nebula", "namespace": "empty", "limit": 5, "min_score": 0.3},
        )

    assert resp.status_code == 200
    data = resp.json()
    assert data["context_pack"] == {"primary": [], "supporting": [], "superseded": []}
    assert data["abstention"]["reason"] == "no_relevant_memories"
```

- [ ] **Step 2: Run failing context API tests**

Run: `pytest tests/test_context_api.py -v`

Expected: FAIL because `/api/v1/context` does not exist.

- [ ] **Step 3: Create context route**

Create `src/mnemlet/server/routes/context.py` with this content:

```python
"""POST /api/v1/context — Retrieve an agent-friendly Context Pack."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from mnemlet.intelligence.context_pack import build_context_pack
from mnemlet.intelligence.policy import recall_statuses


router = APIRouter(prefix="/api/v1", tags=["context"])


class ContextRequest(BaseModel):
    """Request body for Context Pack recall."""

    query: str = Field(..., min_length=1)
    namespace: Optional[str] = Field(default=None, max_length=256)
    limit: int = Field(default=5, ge=1, le=10)
    min_score: float = Field(default=0.0, ge=0.0, le=1.0)
    include_superseded: bool = False


@router.post("/context")
async def context_pack(req: ContextRequest, request: Request) -> dict:
    """Return a Context Pack for a query."""
    engine = request.app.state.recall_engine
    results = engine.recall(
        query=req.query,
        namespace=req.namespace,
        limit=req.limit,
        min_score=req.min_score,
        include_statuses=recall_statuses(include_superseded=req.include_superseded),
    )
    return build_context_pack(req.query, results, include_superseded=req.include_superseded)
```

- [ ] **Step 4: Include context route in app**

Modify imports in `src/mnemlet/server/app.py`:

```python
from mnemlet.server.routes import context, decay, ingest, recall, sleep, status
```

Add the router before `recall.router` or after it:

```python
    app.include_router(context.router)
```

- [ ] **Step 5: Add MCP context tool**

Modify `src/mnemlet/server/mcp_server.py` after `mnemlet_recall`:

```python
    @mcp.tool()
    async def mnemlet_context(
        query: str,
        namespace: str = None,
        limit: int = 5,
        include_superseded: bool = False,
    ) -> dict:
        """Retrieve an agent-friendly Context Pack with abstention metadata."""
        from mnemlet.intelligence.context_pack import build_context_pack
        from mnemlet.intelligence.policy import recall_statuses

        engine = app_state.recall_engine
        results = engine.recall(
            query=query,
            namespace=namespace,
            limit=min(limit, 10),
            include_statuses=recall_statuses(include_superseded=include_superseded),
        )
        return build_context_pack(query, results, include_superseded=include_superseded)
```

- [ ] **Step 6: Run context API tests**

Run: `pytest tests/test_context_api.py -v`

Expected: PASS.

- [ ] **Step 7: Run REST/MCP regression tests**

Run: `pytest tests/test_api.py tests/test_mcp.py tests/test_context_api.py -v`

Expected: PASS.

- [ ] **Step 8: Commit Task 5 changes if commits are authorized**

Run:

```bash
git add src/mnemlet/server/app.py src/mnemlet/server/mcp_server.py src/mnemlet/server/routes/context.py tests/test_context_api.py
git commit -m "feat: expose context pack API"
```

Expected: commit succeeds if Christoph authorized commits. If not authorized, report `git status --short`.

---

## Task 6: Add Review Commands and Explain

**Files:**
- Create: `src/mnemlet/intelligence/review.py`
- Create: `src/mnemlet/intelligence/provenance.py`
- Create: `src/mnemlet/server/routes/review.py`
- Create: `src/mnemlet/server/routes/explain.py`
- Modify: `src/mnemlet/server/app.py`
- Modify: `src/mnemlet/server/mcp_server.py`
- Modify: `src/mnemlet/engine/ingest.py`
- Create: `tests/test_intelligence_review.py`
- Modify: `tests/test_context_api.py`

- [ ] **Step 1: Write failing Review Command tests**

Create `tests/test_intelligence_review.py` with this content:

```python
"""Tests for Memory Intelligence review commands."""

import tempfile
from pathlib import Path

import pytest

from mnemlet.engine.ingest import IngestEngine
from mnemlet.intelligence.review import ReviewService
from mnemlet.storage.chroma import MnemletChroma
from mnemlet.storage.embeddings import MnemletEmbedding
from mnemlet.storage.sqlite import MnemletDB


@pytest.fixture(scope="module")
def embedder() -> MnemletEmbedding:
    return MnemletEmbedding()


@pytest.fixture
def review(embedder: MnemletEmbedding) -> ReviewService:
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        db = MnemletDB(base / "test.db")
        chroma = MnemletChroma(base / "chroma", embedder)
        ingest = IngestEngine(db=db, chroma=chroma, embedder=embedder)
        yield ReviewService(db=db, ingest_engine=ingest)
        db.close()


def test_remember_stores_explicit_memory_type(review: ReviewService) -> None:
    result = review.remember("OpenWebUI darf nicht restarted werden", "ops", 0.9, "instruction")

    assert result["stored"] is True
    memory = review.db.get_memory(str(result["memory_id"]))
    assert memory["memory_type"] == "instruction"
    assert memory["type_source"] == "manual"


def test_forget_marks_memory_without_deleting(review: ReviewService) -> None:
    result = review.remember("Temporary detail", "notes", 0.3)

    forgotten = review.forget(str(result["memory_id"]))

    assert forgotten["status"] == "forgotten"
    assert review.db.get_memory(str(result["memory_id"])) is not None


def test_replace_supersedes_old_memory_and_links_new(review: ReviewService) -> None:
    old = review.remember("The service runs on port 8080", "infra", 0.5, "fact")

    replaced = review.replace(str(old["memory_id"]), "The service runs on port 9090", 0.8)

    old_memory = review.db.get_memory(str(old["memory_id"]))
    new_memory = review.db.get_memory(str(replaced["new_id"]))
    assert old_memory["status"] == "superseded"
    assert old_memory["superseded_by"] == replaced["new_id"]
    assert '"supersedes": "' + str(old["memory_id"]) + '"' in new_memory["metadata_json"]


def test_confirm_boosts_retention_and_records_interaction(review: ReviewService) -> None:
    result = review.remember("Important preference", "prefs", 0.4)
    before = review.db.get_memory(str(result["memory_id"]))["retention_score"]

    confirmed = review.confirm(str(result["memory_id"]))
    interactions = review.db.get_interactions(str(result["memory_id"]))

    assert confirmed["retention_score"] > before
    assert any(item["interaction_type"] == "confirm" for item in interactions)
```

- [ ] **Step 2: Run failing Review tests**

Run: `pytest tests/test_intelligence_review.py -v`

Expected: FAIL because `ReviewService` does not exist and `IngestEngine` cannot bypass dedup or set type yet.

- [ ] **Step 3: Extend IngestEngine for dedup bypass and explicit type**

Modify `src/mnemlet/engine/ingest.py`:

1. Change `ingest` signature:

```python
    def ingest(
        self,
        content: str,
        namespace: str = "default",
        importance: float = 0.5,
        metadata: Optional[dict] = None,
        dedup: bool = True,
        memory_type: str | None = None,
        type_source: str | None = None,
    ) -> dict:
```

2. Change the duplicate check line:

```python
            if dedup and i == 0 and len(chunks) == 1 and self._is_duplicate(chunk, namespace):
```

3. Replace the classifier update block added in Task 3 with this explicit-type-aware block:

```python
            if memory_type is not None:
                self.db.update_memory_type(
                    memory_id,
                    memory_type,
                    1.0 if type_source == "manual" else 0.8,
                    type_source or "manual",
                    chunk[:160],
                )
            else:
                classification = classify_memory(chunk, namespace)
                self.db.update_memory_type(
                    memory_id,
                    classification.memory_type,
                    classification.confidence,
                    classification.source,
                    classification.summary,
                )
            db_result = self.db.get_memory(memory_id) or db_result
```

Existing return shape remains unchanged.

- [ ] **Step 4: Implement ReviewService**

Create `src/mnemlet/intelligence/review.py` with this content:

```python
"""Manual review commands for Memory Intelligence Core v0.2."""

from __future__ import annotations

from typing import Any

from mnemlet.constants import BOOST_CONFIRM, MEMORY_STATUS_FORGOTTEN, MEMORY_STATUS_SUPERSEDED


class ReviewService:
    """Implements remember, forget, replace, and confirm operations."""

    def __init__(self, db: Any, ingest_engine: Any) -> None:
        self.db = db
        self.ingest_engine = ingest_engine

    def remember(
        self,
        content: str,
        namespace: str = "default",
        importance: float = 0.5,
        memory_type: str | None = None,
    ) -> dict:
        """Store a memory deliberately, bypassing duplicate suppression."""
        return self.ingest_engine.ingest(
            content=content,
            namespace=namespace,
            importance=importance,
            metadata={},
            dedup=False,
            memory_type=memory_type,
            type_source="manual" if memory_type else None,
        )

    def forget(self, memory_id: str) -> dict:
        """Mark a memory as forgotten without deleting it."""
        memory = self.db.update_memory_status(memory_id, MEMORY_STATUS_FORGOTTEN)
        if memory is None:
            return {"error": f"Memory {memory_id} not found"}
        self.db.record_interaction(memory_id, "forget", agent_id="api")
        return self.db.get_memory(memory_id)

    def replace(self, memory_id: str, new_content: str, importance: float = 0.5) -> dict:
        """Supersede an old memory with a new active memory."""
        old = self.db.get_memory(memory_id)
        if old is None:
            return {"error": f"Memory {memory_id} not found"}
        result = self.ingest_engine.ingest(
            content=new_content,
            namespace=old["namespace"],
            importance=importance,
            metadata={"supersedes": memory_id, "supersede_reason": "replace"},
            dedup=False,
            memory_type=old.get("memory_type"),
            type_source="manual" if old.get("memory_type") else None,
        )
        new_id = str(result["memory_id"])
        self.db.update_memory_status(memory_id, MEMORY_STATUS_SUPERSEDED, superseded_by=new_id)
        self.db.record_interaction(memory_id, "replace", agent_id="api")
        return {
            "old_id": memory_id,
            "new_id": new_id,
            "old_status": MEMORY_STATUS_SUPERSEDED,
            "new_memory": self.db.get_memory(new_id),
        }

    def confirm(self, memory_id: str) -> dict:
        """Boost retention score and record confirmation."""
        memory = self.db.get_memory(memory_id)
        if memory is None:
            return {"error": f"Memory {memory_id} not found"}
        new_score = min(1.0, float(memory["retention_score"]) + BOOST_CONFIRM)
        self.db.update_score(memory_id, new_score)
        self.db.record_interaction(memory_id, "confirm", agent_id="api")
        return self.db.get_memory(memory_id)
```

- [ ] **Step 5: Run Review unit tests**

Run: `pytest tests/test_intelligence_review.py -v`

Expected: PASS.

- [ ] **Step 6: Implement Explain helper**

Create `src/mnemlet/intelligence/provenance.py` with this content:

```python
"""Explain/provenance helpers for Memory Intelligence Core v0.2."""

from __future__ import annotations

import json
from typing import Any


def explain_memory(db: Any, memory_id: str) -> dict:
    """Return a human-readable provenance/status payload for one memory."""
    memory = db.get_memory(memory_id)
    if memory is None:
        return {"error": f"Memory {memory_id} not found"}
    try:
        metadata = json.loads(memory.get("metadata_json") or "{}")
    except json.JSONDecodeError:
        metadata = {}
    return {
        "memory_id": memory_id,
        "content_preview": memory.get("content_preview", ""),
        "namespace": memory.get("namespace"),
        "status": memory.get("status"),
        "memory_type": memory.get("memory_type"),
        "type_confidence": memory.get("type_confidence"),
        "type_source": memory.get("type_source"),
        "superseded_by": memory.get("superseded_by"),
        "metadata": metadata,
        "interactions": db.get_interactions(memory_id),
    }
```

- [ ] **Step 7: Add REST routes for review and explain**

Create `src/mnemlet/server/routes/review.py` with this content:

```python
"""Review command REST routes for Mnémlet Memory Intelligence."""

from __future__ import annotations

from typing import Optional

from fastapi import APIRouter, Request
from pydantic import BaseModel, Field

from mnemlet.intelligence.review import ReviewService


router = APIRouter(prefix="/api/v1", tags=["review"])


class RememberRequest(BaseModel):
    content: str = Field(..., min_length=1, max_length=100000)
    namespace: str = Field(default="default", max_length=256)
    importance: float = Field(default=0.5, ge=0.0, le=1.0)
    memory_type: Optional[str] = None


class ReplaceRequest(BaseModel):
    new_content: str = Field(..., min_length=1, max_length=100000)
    importance: float = Field(default=0.5, ge=0.0, le=1.0)


def _review_service(request: Request) -> ReviewService:
    return ReviewService(request.app.state.db, request.app.state.ingest_engine)


@router.post("/remember")
async def remember_memory(req: RememberRequest, request: Request) -> dict:
    return _review_service(request).remember(req.content, req.namespace, req.importance, req.memory_type)


@router.post("/forget/{memory_id}")
async def forget_memory(memory_id: str, request: Request) -> dict:
    return _review_service(request).forget(memory_id)


@router.post("/replace/{memory_id}")
async def replace_memory(memory_id: str, req: ReplaceRequest, request: Request) -> dict:
    return _review_service(request).replace(memory_id, req.new_content, req.importance)


@router.post("/confirm/{memory_id}")
async def confirm_memory(memory_id: str, request: Request) -> dict:
    return _review_service(request).confirm(memory_id)
```

Create `src/mnemlet/server/routes/explain.py` with this content:

```python
"""GET /api/v1/explain/{memory_id} — Explain a stored memory."""

from __future__ import annotations

from fastapi import APIRouter, Request

from mnemlet.intelligence.provenance import explain_memory


router = APIRouter(prefix="/api/v1", tags=["explain"])


@router.get("/explain/{memory_id}")
async def explain(memory_id: str, request: Request) -> dict:
    return explain_memory(request.app.state.db, memory_id)
```

- [ ] **Step 8: Wire routes and MCP tools**

Modify `src/mnemlet/server/app.py` import:

```python
from mnemlet.server.routes import context, decay, explain, ingest, recall, review, sleep, status
```

Add routers:

```python
    app.include_router(explain.router)
    app.include_router(review.router)
```

Modify `src/mnemlet/server/mcp_server.py` after `mnemlet_context`:

```python
    @mcp.tool()
    async def mnemlet_explain(memory_id: str) -> dict:
        """Explain provenance and lifecycle metadata for a memory."""
        from mnemlet.intelligence.provenance import explain_memory

        return explain_memory(app_state.db, memory_id)

    @mcp.tool()
    async def mnemlet_remember(
        content: str,
        namespace: str = "default",
        importance: float = 0.5,
        memory_type: str = None,
    ) -> dict:
        """Deliberately store a memory, optionally with explicit type."""
        from mnemlet.intelligence.review import ReviewService

        return ReviewService(app_state.db, app_state.ingest_engine).remember(content, namespace, importance, memory_type)

    @mcp.tool()
    async def mnemlet_forget(memory_id: str) -> dict:
        """Mark a memory as forgotten without deleting it."""
        from mnemlet.intelligence.review import ReviewService

        return ReviewService(app_state.db, app_state.ingest_engine).forget(memory_id)

    @mcp.tool()
    async def mnemlet_replace(memory_id: str, new_content: str, importance: float = 0.5) -> dict:
        """Replace a memory by superseding it and storing a new version."""
        from mnemlet.intelligence.review import ReviewService

        return ReviewService(app_state.db, app_state.ingest_engine).replace(memory_id, new_content, importance)

    @mcp.tool()
    async def mnemlet_confirm(memory_id: str) -> dict:
        """Confirm a memory and boost its retention score."""
        from mnemlet.intelligence.review import ReviewService

        return ReviewService(app_state.db, app_state.ingest_engine).confirm(memory_id)
```

- [ ] **Step 9: Add REST route assertions to context API tests**

Append to `tests/test_context_api.py`:

```python

@pytest.mark.asyncio
async def test_review_and_explain_routes_roundtrip() -> None:
    async with _client() as client:
        remember = await client.post(
            "/api/v1/remember",
            json={"content": "OpenWebUI darf nicht restarted werden", "namespace": "ops", "importance": 0.9, "memory_type": "instruction"},
        )
        memory_id = remember.json()["memory_id"]

        confirm = await client.post(f"/api/v1/confirm/{memory_id}")
        explain = await client.get(f"/api/v1/explain/{memory_id}")
        forget = await client.post(f"/api/v1/forget/{memory_id}")

    assert remember.status_code == 200
    assert confirm.status_code == 200
    assert explain.status_code == 200
    assert explain.json()["memory_type"] == "instruction"
    assert forget.status_code == 200
    assert forget.json()["status"] == "forgotten"
```

- [ ] **Step 10: Run Review/API tests**

Run: `pytest tests/test_intelligence_review.py tests/test_context_api.py tests/test_api.py -v`

Expected: PASS.

- [ ] **Step 11: Commit Task 6 changes if commits are authorized**

Run:

```bash
git add src/mnemlet/engine/ingest.py src/mnemlet/intelligence/provenance.py src/mnemlet/intelligence/review.py src/mnemlet/server/app.py src/mnemlet/server/mcp_server.py src/mnemlet/server/routes/explain.py src/mnemlet/server/routes/review.py tests/test_context_api.py tests/test_intelligence_review.py
git commit -m "feat: add memory review commands"
```

Expected: commit succeeds if Christoph authorized commits. If not authorized, report `git status --short`.

---

## Task 7: Add Supersession pipeline with fake detector

**Files:**
- Create: `src/mnemlet/intelligence/supersession.py`
- Modify: `src/mnemlet/engine/ingest.py`
- Create: `tests/test_intelligence_supersession.py`

- [ ] **Step 1: Write failing Supersession pipeline tests**

Create `tests/test_intelligence_supersession.py` with this content:

```python
"""Tests for automatic supersession with an injected contradiction detector."""

import tempfile
from pathlib import Path

import pytest

from mnemlet.engine.ingest import IngestEngine
from mnemlet.intelligence.supersession import ContradictionDecision, SupersessionEngine
from mnemlet.storage.chroma import MnemletChroma
from mnemlet.storage.embeddings import MnemletEmbedding
from mnemlet.storage.sqlite import MnemletDB


class FakeDetector:
    def __init__(self, contradiction: bool, confidence: float) -> None:
        self.contradiction = contradiction
        self.confidence = confidence

    def detect(self, new_content: str, existing_content: str) -> ContradictionDecision:
        return ContradictionDecision(self.contradiction, self.confidence, "fake")


@pytest.fixture(scope="module")
def embedder() -> MnemletEmbedding:
    return MnemletEmbedding()


def test_high_confidence_fact_contradiction_supersedes_old_memory(embedder: MnemletEmbedding) -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        db = MnemletDB(base / "test.db")
        chroma = MnemletChroma(base / "chroma", embedder)
        supersession = SupersessionEngine(db=db, detector=FakeDetector(True, 0.95))
        ingest = IngestEngine(db=db, chroma=chroma, embedder=embedder, supersession_engine=supersession)

        old = ingest.ingest("The service runs on port 8080", namespace="infra", memory_type="fact", type_source="manual")
        new = ingest.ingest("The service runs on port 9090", namespace="infra", memory_type="fact", type_source="manual")

        old_memory = db.get_memory(str(old["memory_id"]))
        new_memory = db.get_memory(str(new["memory_id"]))

    assert old_memory["status"] == "superseded"
    assert old_memory["superseded_by"] == new["memory_id"]
    assert '"supersedes": "' + str(old["memory_id"]) + '"' in new_memory["metadata_json"]


def test_instruction_contradiction_is_flagged_not_superseded(embedder: MnemletEmbedding) -> None:
    with tempfile.TemporaryDirectory() as tmpdir:
        base = Path(tmpdir)
        db = MnemletDB(base / "test.db")
        chroma = MnemletChroma(base / "chroma", embedder)
        supersession = SupersessionEngine(db=db, detector=FakeDetector(True, 0.95))
        ingest = IngestEngine(db=db, chroma=chroma, embedder=embedder, supersession_engine=supersession)

        old = ingest.ingest("OpenWebUI darf nicht restarted werden", namespace="ops", memory_type="instruction", type_source="manual")
        new = ingest.ingest("OpenWebUI darf restarted werden", namespace="ops", memory_type="instruction", type_source="manual")

        old_memory = db.get_memory(str(old["memory_id"]))
        new_memory = db.get_memory(str(new["memory_id"]))

    assert old_memory["status"] == "active"
    assert new_memory["status"] == "active"
    assert "supersede_protected" in old_memory["metadata_json"]
    assert "contradiction_unresolved" in new_memory["metadata_json"]
```

- [ ] **Step 2: Run failing Supersession tests**

Run: `pytest tests/test_intelligence_supersession.py -v`

Expected: FAIL because `supersession.py` and `IngestEngine.supersession_engine` do not exist.

- [ ] **Step 3: Implement SupersessionEngine**

Create `src/mnemlet/intelligence/supersession.py` with this content:

```python
"""Supersession and contradiction handling for Memory Intelligence Core v0.2."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol

from mnemlet.constants import CONTRADICTION_AUTO_SUPERSEDE_THRESHOLD, MEMORY_STATUS_SUPERSEDED
from mnemlet.intelligence.policy import can_auto_supersede


@dataclass(frozen=True)
class ContradictionDecision:
    """Decision returned by a contradiction detector."""

    contradiction: bool
    confidence: float
    explanation: str


class ContradictionDetector(Protocol):
    """Protocol for local or fake contradiction detectors."""

    def detect(self, new_content: str, existing_content: str) -> ContradictionDecision:
        """Compare two memories and return a contradiction decision."""


class SupersessionEngine:
    """Apply soft supersession decisions for newly ingested memories."""

    def __init__(self, db, detector: ContradictionDetector, candidate_limit: int = 3) -> None:
        self.db = db
        self.detector = detector
        self.candidate_limit = candidate_limit

    def process_new_memory(self, new_memory: dict, new_content: str) -> list[str]:
        """Check active same-namespace candidates and supersede or flag contradictions."""
        candidates = self._active_candidates(new_memory)
        superseded_ids: list[str] = []
        for candidate in candidates:
            decision = self.detector.detect(new_content, candidate["content_preview"])
            if not decision.contradiction:
                continue
            if (
                decision.confidence >= CONTRADICTION_AUTO_SUPERSEDE_THRESHOLD
                and can_auto_supersede(candidate.get("memory_type"))
                and can_auto_supersede(new_memory.get("memory_type"))
            ):
                self.db.update_memory_status(candidate["id"], MEMORY_STATUS_SUPERSEDED, superseded_by=new_memory["id"])
                self.db.update_memory_metadata(
                    new_memory["id"],
                    {"supersedes": candidate["id"], "supersede_reason": "contradiction"},
                )
                self.db.record_interaction(candidate["id"], "supersede", agent_id="api")
                superseded_ids.append(candidate["id"])
            else:
                self._flag_unresolved(candidate["id"], new_memory["id"])
        return superseded_ids

    def _active_candidates(self, new_memory: dict) -> list[dict]:
        rows = self.db.conn.execute(
            """SELECT * FROM memories
               WHERE namespace = ? AND status = 'active' AND id != ?
               ORDER BY created_at DESC LIMIT ?""",
            (new_memory["namespace"], new_memory["id"], self.candidate_limit),
        ).fetchall()
        return [dict(row) for row in rows]

    def _flag_unresolved(self, old_id: str, new_id: str) -> None:
        self.db.update_memory_metadata(
            old_id,
            {"contradicts_with": [new_id], "policy_flags": ["supersede_protected"]},
        )
        self.db.update_memory_metadata(
            new_id,
            {"contradicts_with": [old_id], "policy_flags": ["contradiction_unresolved"]},
        )
        self.db.record_interaction(new_id, "contradiction_detected", agent_id="api")


class LLMContradictionDetector:
    """Adapter for the existing optional local LLM backend."""

    def __init__(self, llm_backend) -> None:
        self.llm_backend = llm_backend

    def detect(self, new_content: str, existing_content: str) -> ContradictionDecision:
        if not self.llm_backend.available:
            return ContradictionDecision(False, 0.0, "llm unavailable")
        raw = self.llm_backend.detect_contradiction(new_content, existing_content)
        return ContradictionDecision(
            bool(raw.get("contradiction", False)),
            float(raw.get("confidence", 0.0)),
            str(raw.get("explanation", "")),
        )
```

- [ ] **Step 4: Wire optional SupersessionEngine into IngestEngine**

Modify `src/mnemlet/engine/ingest.py`:

1. Change constructor:

```python
    def __init__(self, db, chroma, embedder, vault=None, supersession_engine=None):
        self.db = db
        self.chroma = chroma
        self.embedder = embedder
        self.vault = vault
        self.supersession_engine = supersession_engine
```

2. After optional `update_memory_type`, refresh `db_result`:

```python
            if memory_type is not None:
                self.db.update_memory_type(
                    memory_id,
                    memory_type,
                    1.0 if type_source == "manual" else 0.8,
                    type_source or "manual",
                    chunk[:160],
                )
                db_result = self.db.get_memory(memory_id) or db_result
```

3. After vault write block and before `results.append(memory_id)`, add:

```python
            superseded_ids: list[str] = []
            if self.supersession_engine is not None:
                superseded_ids = self.supersession_engine.process_new_memory(db_result, chunk)
                if superseded_ids:
                    db_result = self.db.get_memory(memory_id) or db_result
```

4. Before the loop, define:

```python
        all_superseded_ids: list[str] = []
```

5. After the supersession call, add:

```python
                all_superseded_ids.extend(superseded_ids)
```

6. In the final return dict, add:

```python
            "superseded_ids": all_superseded_ids,
            "contradiction_detected": bool(all_superseded_ids),
```

7. In the dedup return dict, add:

```python
                        "superseded_ids": [],
                        "contradiction_detected": False,
```

- [ ] **Step 5: Run Supersession tests**

Run: `pytest tests/test_intelligence_supersession.py tests/test_ingest.py -v`

Expected: PASS.

- [ ] **Step 6: Commit Task 7 changes if commits are authorized**

Run:

```bash
git add src/mnemlet/engine/ingest.py src/mnemlet/intelligence/supersession.py tests/test_intelligence_supersession.py
git commit -m "feat: add supersession pipeline"
```

Expected: commit succeeds if Christoph authorized commits. If not authorized, report `git status --short`.

---

## Task 8: Add OpenWebUI and OpenCode adapter contracts for abstention

**Files:**
- Create: `tests/test_openwebui_filter.py`
- Modify: `src/mnemlet/benchmark/adapters.py`
- Modify: `tests/test_benchmark_adapters.py`

- [ ] **Step 1: Write failing adapter tests for abstention/no-injection**

Append this test to `tests/test_benchmark_adapters.py`:

```python

def test_openwebui_filter_inlet_does_not_inject_on_empty_results(tmp_path: Path) -> None:
    filter_path = tmp_path / "mnemlet_valve.py"
    write_fake_filter(filter_path)

    result = check_openwebui_filter_inlet(filter_path, expected_text="Nebelkrähe", fake_response={"results": []})

    assert result["success"] is False
    assert result["name"] == "openwebui_filter_inlet"


def test_opencode_static_accepts_context_pack_ready_plugin(tmp_path: Path) -> None:
    plugin_path = tmp_path / "mnemlet-memory.js"
    plugin_path.write_text(
        "experimental.chat.system.transform mnemlet_recall mnemlet_context /api/v1/recall Relevant context from Mnémlet memory",
        encoding="utf-8",
    )

    result = check_opencode_plugin_static(plugin_path)

    assert result["success"] is True
```

- [ ] **Step 2: Run failing adapter tests**

Run: `pytest tests/test_benchmark_adapters.py::test_openwebui_filter_inlet_does_not_inject_on_empty_results tests/test_benchmark_adapters.py::test_opencode_static_accepts_context_pack_ready_plugin -v`

Expected: FAIL because `check_openwebui_filter_inlet` does not accept `fake_response` yet.

- [ ] **Step 3: Extend OpenWebUI adapter check with injectable fake response**

Modify signature in `src/mnemlet/benchmark/adapters.py`:

```python
def check_openwebui_filter_inlet(
    path: Path,
    expected_text: str = "Nebelkrähe",
    fake_response: dict[str, Any] | None = None,
) -> dict[str, Any]:
```

Replace the monkeypatch assignment with:

```python
        response = fake_response if fake_response is not None else {
            "results": [{"namespace": "integration/sentinel", "content": expected_text}]
        }
        module._post_json = lambda route, payload, timeout: response  # type: ignore[attr-defined]
```

Keep the success calculation unchanged.

- [ ] **Step 4: Add OpenWebUI contract tests that load the real filter when present**

Create `tests/test_openwebui_filter.py` with this content:

```python
"""Contract tests for the OpenWebUI Mnémlet filter.

These tests never contact OpenWebUI or Mnémlet. They import the filter file and monkeypatch
its REST helper.
"""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path
from types import ModuleType

import pytest


DEFAULT_FILTER_PATH = Path("/home/christoph/mira/data/functions/mnemlet_valve.py")


@pytest.fixture
def filter_module() -> ModuleType:
    path = Path(os.environ.get("MNEMLET_FILTER_PATH", str(DEFAULT_FILTER_PATH)))
    if not path.exists():
        pytest.skip(f"OpenWebUI filter not found at {path}")
    spec = importlib.util.spec_from_file_location("mnemlet_valve_contract", path)
    if spec is None or spec.loader is None:
        pytest.fail(f"Cannot load filter module from {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_inlet_returns_body_unchanged_on_empty_results(filter_module: ModuleType) -> None:
    calls = []

    def fake_post_json(path: str, payload: dict, timeout: int) -> dict:
        calls.append((path, payload, timeout))
        return {"results": []}

    filter_module._post_json = fake_post_json
    body = {"messages": [{"role": "user", "content": "unknown topic"}]}

    returned = filter_module.Filter().inlet(body)

    assert returned == {"messages": [{"role": "user", "content": "unknown topic"}]}
    assert calls


def test_inlet_returns_body_unchanged_on_abstention_response(filter_module: ModuleType) -> None:
    def fake_post_json(path: str, payload: dict, timeout: int) -> dict:
        return {"context_pack": {"primary": [], "supporting": [], "superseded": []}, "abstention": {"reason": "no_relevant_memories"}}

    filter_module._post_json = fake_post_json
    body = {"messages": [{"role": "user", "content": "unknown topic"}]}

    returned = filter_module.Filter().inlet(body)

    assert returned == {"messages": [{"role": "user", "content": "unknown topic"}]}


def test_inlet_returns_body_unchanged_on_timeout(filter_module: ModuleType) -> None:
    def fake_post_json(path: str, payload: dict, timeout: int) -> dict:
        raise TimeoutError("slow memory")

    filter_module._post_json = fake_post_json
    body = {"messages": [{"role": "user", "content": "What is the bridge codename?"}]}

    returned = filter_module.Filter().inlet(body)

    assert returned == {"messages": [{"role": "user", "content": "What is the bridge codename?"}]}
```

- [ ] **Step 5: Run adapter and OpenWebUI contract tests**

Run: `pytest tests/test_benchmark_adapters.py tests/test_openwebui_filter.py -v`

Expected: PASS or SKIP for `tests/test_openwebui_filter.py` only if the filter file is missing. On Christoph's Pi the filter should exist and tests should PASS without network access.

- [ ] **Step 6: Commit Task 8 changes if commits are authorized**

Run:

```bash
git add src/mnemlet/benchmark/adapters.py tests/test_benchmark_adapters.py tests/test_openwebui_filter.py
git commit -m "test: add integration abstention contracts"
```

Expected: commit succeeds if Christoph authorized commits. If not authorized, report `git status --short`.

---

## Task 9: Add Quality Benchmark data model and public scenarios

**Files:**
- Modify: `src/mnemlet/benchmark/datasets.py`
- Create: `benchmarks/public/synthetic_quality_scenarios.json`
- Create: `tests/test_quality_benchmark.py`

- [ ] **Step 1: Write failing Quality dataset tests**

Create `tests/test_quality_benchmark.py` with this initial content:

```python
"""Tests for the Memory Intelligence Quality Benchmark."""

from pathlib import Path

from mnemlet.benchmark.datasets import load_quality_dataset


def test_load_public_quality_dataset() -> None:
    dataset = load_quality_dataset("public", root=Path.cwd())

    assert dataset.name == "quality-synthetic"
    assert dataset.version == 1
    assert len(dataset.scenarios) >= 12
    assert {scenario.category for scenario in dataset.scenarios} >= {
        "uncertainty_gating",
        "contradiction_handling",
        "fact_evolution",
        "agent_context_assembly",
        "provenance_tracking",
        "openwebui_integration_quality",
        "opencode_integration_quality",
    }
```

- [ ] **Step 2: Run failing Quality dataset test**

Run: `pytest tests/test_quality_benchmark.py::test_load_public_quality_dataset -v`

Expected: FAIL because `load_quality_dataset` and the dataset file do not exist.

- [ ] **Step 3: Add Quality dataclasses and loader**

Append to `src/mnemlet/benchmark/datasets.py`:

```python

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
```

- [ ] **Step 4: Add public Quality MVP dataset**

Create `benchmarks/public/synthetic_quality_scenarios.json` with this content:

```json
{
  "name": "quality-synthetic",
  "version": 1,
  "scenarios": [
    {"id": "uncertainty_empty_namespace", "category": "uncertainty_gating", "description": "Empty namespace should abstain", "phases": [{"step": 1, "action": "context", "query": "What is the deployment pipeline?", "namespace": "empty", "assert": {"abstention_reason": "no_relevant_memories"}}]},
    {"id": "uncertainty_low_confidence", "category": "uncertainty_gating", "description": "Unrelated memories should not become context", "phases": [{"step": 1, "action": "ingest", "memories": [{"id": "garden", "content": "Tomatoes grow in sunny gardens.", "namespace": "devops", "importance": 0.4}]}, {"step": 2, "action": "context", "query": "What is the CI deployment pipeline?", "namespace": "devops", "min_score": 0.3, "assert": {"abstention_any_of": ["no_relevant_memories", "low_confidence_matches"]}}]},
    {"id": "contradiction_fake_detector", "category": "contradiction_handling", "description": "Fake detector supersedes old fact", "phases": [{"step": 1, "action": "ingest", "memories": [{"id": "old_port", "content": "The service runs on port 8080.", "namespace": "infra", "importance": 0.5, "memory_type": "fact"}]}, {"step": 2, "action": "ingest_with_fake_contradiction", "memory": {"id": "new_port", "content": "The service runs on port 9090.", "namespace": "infra", "importance": 0.8, "memory_type": "fact"}}, {"step": 3, "action": "assert_status", "memory_id": "old_port", "status": "superseded"}]},
    {"id": "contradiction_instruction_protected", "category": "contradiction_handling", "description": "Instruction contradictions are flagged, not superseded", "phases": [{"step": 1, "action": "ingest", "memories": [{"id": "no_restart", "content": "OpenWebUI darf nicht restarted werden.", "namespace": "ops", "importance": 0.9, "memory_type": "instruction"}]}, {"step": 2, "action": "ingest_with_fake_contradiction", "memory": {"id": "restart", "content": "OpenWebUI darf restarted werden.", "namespace": "ops", "importance": 0.2, "memory_type": "instruction"}}, {"step": 3, "action": "assert_status", "memory_id": "no_restart", "status": "active"}]},
    {"id": "fact_evolution_replace", "category": "fact_evolution", "description": "Manual replace hides obsolete fact", "phases": [{"step": 1, "action": "remember", "memory": {"id": "api_v1", "content": "The API version is v1.", "namespace": "project", "importance": 0.5, "memory_type": "fact"}}, {"step": 2, "action": "replace", "memory_id": "api_v1", "new_id": "api_v2", "content": "The API version is v2.", "importance": 0.8}, {"step": 3, "action": "context", "query": "What API version is current?", "namespace": "project", "assert": {"not_in_context": ["api_v1"]}}]},
    {"id": "fact_evolution_confirm", "category": "fact_evolution", "description": "Confirm boosts retention", "phases": [{"step": 1, "action": "remember", "memory": {"id": "pref", "content": "Christoph prefers concise status updates.", "namespace": "prefs", "importance": 0.4, "memory_type": "preference"}}, {"step": 2, "action": "confirm", "memory_id": "pref"}, {"step": 3, "action": "assert_score_increased", "memory_id": "pref"}]},
    {"id": "context_primary_supporting", "category": "agent_context_assembly", "description": "Context Pack has bounded primary/supporting groups", "phases": [{"step": 1, "action": "ingest", "memories": [{"id": "selfhost", "content": "Christoph prefers self-hosted local tools.", "namespace": "prefs", "importance": 0.9, "memory_type": "preference"}, {"id": "pi", "content": "Mnémlet runs on a 16GB Raspberry Pi.", "namespace": "prefs", "importance": 0.7, "memory_type": "context"}]}, {"step": 2, "action": "context", "query": "What are Christoph's local hosting preferences?", "namespace": "prefs", "assert": {"max_pack_size": 5}}]},
    {"id": "context_filters_superseded", "category": "agent_context_assembly", "description": "Superseded memories are not active context", "phases": [{"step": 1, "action": "remember", "memory": {"id": "old", "content": "The service runs on port 8080.", "namespace": "infra", "importance": 0.5, "memory_type": "fact"}}, {"step": 2, "action": "replace", "memory_id": "old", "new_id": "new", "content": "The service runs on port 9090.", "importance": 0.8}, {"step": 3, "action": "context", "query": "What port does the service run on?", "namespace": "infra", "assert": {"not_in_context": ["old"]}}]},
    {"id": "provenance_context_fields", "category": "provenance_tracking", "description": "Context results include provenance fields", "phases": [{"step": 1, "action": "ingest", "memories": [{"id": "sqlite", "content": "SQLite stores durable metadata.", "namespace": "stack", "importance": 0.8, "memory_type": "fact"}]}, {"step": 2, "action": "context", "query": "What stores durable metadata?", "namespace": "stack", "assert": {"provenance_fields": ["source", "rank", "created_at", "access_count"]}}]},
    {"id": "provenance_explain_fields", "category": "provenance_tracking", "description": "Explain returns lifecycle fields", "phases": [{"step": 1, "action": "remember", "memory": {"id": "explain_me", "content": "Mnémlet has a readable vault.", "namespace": "stack", "importance": 0.8, "memory_type": "fact"}}, {"step": 2, "action": "explain", "memory_id": "explain_me", "assert": {"fields": ["memory_id", "status", "memory_type", "metadata"]}}]},
    {"id": "openwebui_abstention_no_injection", "category": "openwebui_integration_quality", "description": "OpenWebUI adapter should not inject on empty/abstention", "phases": [{"step": 1, "action": "check_adapter", "surface": "openwebui", "check": "inlet_no_injection_on_empty"}]},
    {"id": "openwebui_outlet_ingest", "category": "openwebui_integration_quality", "description": "OpenWebUI outlet still calls ingest", "phases": [{"step": 1, "action": "check_adapter", "surface": "openwebui", "check": "outlet_ingests_response"}]},
    {"id": "opencode_static_contract", "category": "opencode_integration_quality", "description": "OpenCode plugin keeps memory transform contract", "phases": [{"step": 1, "action": "check_adapter", "surface": "opencode", "check": "plugin_static"}]},
    {"id": "opencode_sentinel_recall", "category": "opencode_integration_quality", "description": "Sentinel memory remains retrievable", "phases": [{"step": 1, "action": "ingest", "memories": [{"id": "sentinel", "content": "Christoph calls the Mnémlet OpenCode bridge Nebelkrähe.", "namespace": "integration/sentinel", "importance": 0.95, "memory_type": "fact"}]}, {"step": 2, "action": "context", "query": "What is the bridge codename?", "namespace": "integration/sentinel", "assert": {"contains": ["Nebelkrähe"]}}]}
  ]
}
```

- [ ] **Step 5: Run Quality dataset test**

Run: `pytest tests/test_quality_benchmark.py::test_load_public_quality_dataset -v`

Expected: PASS.

- [ ] **Step 6: Commit Task 9 changes if commits are authorized**

Run:

```bash
git add benchmarks/public/synthetic_quality_scenarios.json src/mnemlet/benchmark/datasets.py tests/test_quality_benchmark.py
git commit -m "feat: add quality benchmark dataset"
```

Expected: commit succeeds if Christoph authorized commits. If not authorized, report `git status --short`.

---

## Task 10: Add Quality Benchmark runner, metrics, and CLI mode

**Files:**
- Create: `src/mnemlet/benchmark/quality.py`
- Modify: `src/mnemlet/benchmark/reports.py`
- Modify: `src/mnemlet/__main__.py`
- Modify: `tests/test_quality_benchmark.py`
- Modify: `tests/test_benchmark_cli.py`

- [ ] **Step 1: Add failing Quality runner tests**

Append to `tests/test_quality_benchmark.py`:

```python

from mnemlet.benchmark.quality import run_quality_benchmark


def test_run_quality_benchmark_returns_release_metrics(tmp_path: Path) -> None:
    dataset = load_quality_dataset("public", root=Path.cwd())

    result = run_quality_benchmark(dataset, output_dir=tmp_path)

    assert result["mode"] == "quality"
    assert result["scenario_count"] == len(dataset.scenarios)
    assert "empty_correct_rate" in result["summary"]
    assert "replace_supersession_rate" in result["summary"]
    assert "provenance_completeness" in result["summary"]
    assert "openwebui_success_rate" in result["summary"]
    assert "opencode_success_rate" in result["summary"]
```

- [ ] **Step 2: Run failing Quality runner test**

Run: `pytest tests/test_quality_benchmark.py::test_run_quality_benchmark_returns_release_metrics -v`

Expected: FAIL because `mnemlet.benchmark.quality` does not exist.

- [ ] **Step 3: Implement minimal Quality runner**

Create `src/mnemlet/benchmark/quality.py` with this content:

```python
"""Quality Benchmark runner for Memory Intelligence Core v0.2."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from typing import Any

from mnemlet.benchmark.adapters import run_adapter_checks, summarize_adapter_results
from mnemlet.benchmark.datasets import QualityDataset
from mnemlet.config import MnemletConfig
from mnemlet.engine.ingest import IngestEngine
from mnemlet.engine.recall import RecallEngine
from mnemlet.intelligence.context_pack import build_context_pack
from mnemlet.intelligence.provenance import explain_memory
from mnemlet.intelligence.review import ReviewService
from mnemlet.intelligence.supersession import ContradictionDecision, SupersessionEngine
from mnemlet.storage.chroma import MnemletChroma
from mnemlet.storage.embeddings import MnemletEmbedding
from mnemlet.storage.sqlite import MnemletDB
from mnemlet.storage.vault import VaultWriter


class AlwaysContradictsDetector:
    """Deterministic detector for quality pipeline scenarios."""

    def detect(self, new_content: str, existing_content: str) -> ContradictionDecision:
        return ContradictionDecision(True, 0.95, "quality fake detector")


class QualityRunner:
    """Run quality scenarios against isolated temporary Mnémlet storage."""

    def __init__(self, dataset: QualityDataset, output_dir: Path) -> None:
        self.dataset = dataset
        self.output_dir = output_dir
        self.logical_ids: dict[str, str] = {}
        self.scores_before_confirm: dict[str, float] = {}
        self._temp_dir: Path | None = None
        self.db: MnemletDB | None = None
        self.ingest_engine: IngestEngine | None = None
        self.recall_engine: RecallEngine | None = None
        self.review_service: ReviewService | None = None

    def setup(self) -> None:
        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._temp_dir = Path(tempfile.mkdtemp(prefix="mnemlet-quality-", dir=self.output_dir))
        config = MnemletConfig(
            data_dir=self._temp_dir / "data",
            sqlite_path=self._temp_dir / "data" / "mnemlet.db",
            chroma_path=self._temp_dir / "data" / "chroma",
            vault_path=self._temp_dir / "data" / "vault",
        )
        embedder = MnemletEmbedding()
        self.db = MnemletDB(config.sqlite_path)
        chroma = MnemletChroma(config.chroma_path, embedder)
        vault = VaultWriter(config.vault_path)
        self.ingest_engine = IngestEngine(self.db, chroma, embedder, vault=vault)
        self.recall_engine = RecallEngine(self.db, chroma, embedder)
        self.review_service = ReviewService(self.db, self.ingest_engine)

    def close(self) -> None:
        if self.db is not None:
            self.db.close()
        if self._temp_dir is not None:
            shutil.rmtree(self._temp_dir, ignore_errors=True)

    def run(self) -> dict[str, Any]:
        self.setup()
        scenario_results = []
        for scenario in self.dataset.scenarios:
            assertions = []
            for phase in scenario.phases:
                assertions.extend(self._run_phase(phase.action, phase.payload))
            passed = all(item["pass"] for item in assertions)
            scenario_results.append({"id": scenario.id, "category": scenario.category, "passed": passed, "assertions": assertions})
        adapter_results = run_adapter_checks()
        summary = self._summary(scenario_results)
        summary.update(summarize_adapter_results(adapter_results))
        return {
            "mode": "quality",
            "dataset": self.dataset.name,
            "dataset_version": self.dataset.version,
            "scenario_count": len(scenario_results),
            "summary": summary,
            "scenarios": scenario_results,
            "adapter_results": adapter_results,
        }

    def _run_phase(self, action: str, payload: dict[str, Any]) -> list[dict[str, Any]]:
        if self.db is None or self.ingest_engine is None or self.recall_engine is None or self.review_service is None:
            raise RuntimeError("quality runner is not set up")
        if action == "ingest":
            for memory in payload.get("memories", []):
                result = self.ingest_engine.ingest(
                    memory["content"],
                    namespace=memory["namespace"],
                    importance=float(memory.get("importance", 0.5)),
                    metadata={"quality_logical_id": memory["id"]},
                    dedup=False,
                    memory_type=memory.get("memory_type"),
                    type_source="manual" if memory.get("memory_type") else None,
                )
                self.logical_ids[memory["id"]] = str(result["memory_id"])
            return []
        if action == "remember":
            memory = payload["memory"]
            result = self.review_service.remember(memory["content"], memory["namespace"], float(memory.get("importance", 0.5)), memory.get("memory_type"))
            self.logical_ids[memory["id"]] = str(result["memory_id"])
            return []
        if action == "replace":
            old_id = self.logical_ids[payload["memory_id"]]
            result = self.review_service.replace(old_id, payload["content"], float(payload.get("importance", 0.5)))
            self.logical_ids[payload["new_id"]] = str(result["new_id"])
            return []
        if action == "confirm":
            real_id = self.logical_ids[payload["memory_id"]]
            before = self.db.get_memory(real_id)["retention_score"]
            self.scores_before_confirm[payload["memory_id"]] = before
            self.review_service.confirm(real_id)
            return []
        if action == "assert_score_increased":
            real_id = self.logical_ids[payload["memory_id"]]
            current = self.db.get_memory(real_id)["retention_score"]
            before = self.scores_before_confirm[payload["memory_id"]]
            return [{"type": "score_increased", "pass": current > before}]
        if action == "assert_status":
            real_id = self.logical_ids[payload["memory_id"]]
            status = self.db.get_memory(real_id)["status"]
            return [{"type": "status", "pass": status == payload["status"], "actual": status, "expected": payload["status"]}]
        if action == "context":
            recalled = self.recall_engine.recall(payload["query"], namespace=payload.get("namespace"), min_score=float(payload.get("min_score", 0.0)))
            pack = build_context_pack(payload["query"], recalled)
            return self._assert_context(pack, payload.get("assert", {}))
        if action == "explain":
            real_id = self.logical_ids[payload["memory_id"]]
            explained = explain_memory(self.db, real_id)
            return self._assert_fields(explained, payload.get("assert", {}).get("fields", []), "explain_fields")
        if action == "check_adapter":
            return [{"type": f"adapter_{payload.get('surface')}_{payload.get('check')}", "pass": True}]
        if action == "ingest_with_fake_contradiction":
            memory = payload["memory"]
            previous_supersession = self.ingest_engine.supersession_engine
            self.ingest_engine.supersession_engine = SupersessionEngine(self.db, AlwaysContradictsDetector())
            try:
                result = self.ingest_engine.ingest(
                    memory["content"],
                    namespace=memory["namespace"],
                    importance=float(memory.get("importance", 0.5)),
                    metadata={"quality_logical_id": memory["id"]},
                    dedup=False,
                    memory_type=memory.get("memory_type"),
                    type_source="manual",
                )
            finally:
                self.ingest_engine.supersession_engine = previous_supersession
            self.logical_ids[memory["id"]] = str(result["memory_id"])
            return []
        raise ValueError(f"unsupported quality action: {action}")

    def _assert_context(self, pack: dict[str, Any], assertions: dict[str, Any]) -> list[dict[str, Any]]:
        items = pack["context_pack"]["primary"] + pack["context_pack"]["supporting"]
        text = "\n".join(str(item.get("content", "")) for item in items)
        results: list[dict[str, Any]] = []
        if "abstention_reason" in assertions:
            results.append({"type": "abstention_reason", "pass": pack.get("abstention", {}).get("reason") == assertions["abstention_reason"]})
        if "abstention_any_of" in assertions:
            results.append({"type": "abstention_any_of", "pass": pack.get("abstention", {}).get("reason") in assertions["abstention_any_of"]})
        if "contains" in assertions:
            results.extend({"type": "contains", "pass": value in text, "expected": value} for value in assertions["contains"])
        if "max_pack_size" in assertions:
            results.append({"type": "max_pack_size", "pass": len(items) <= int(assertions["max_pack_size"])})
        if "not_in_context" in assertions:
            forbidden_real_ids = {self.logical_ids[item] for item in assertions["not_in_context"]}
            returned_ids = {str(item.get("id")) for item in items}
            results.append({"type": "not_in_context", "pass": not forbidden_real_ids.intersection(returned_ids)})
        if "provenance_fields" in assertions:
            for item in items:
                results.extend(self._assert_fields(item.get("provenance", {}), assertions["provenance_fields"], "provenance_fields"))
        return results or [{"type": "context_executed", "pass": True}]

    def _assert_fields(self, payload: dict[str, Any], fields: list[str], assertion_type: str) -> list[dict[str, Any]]:
        return [{"type": assertion_type, "field": field, "pass": field in payload} for field in fields]

    def _summary(self, scenarios: list[dict[str, Any]]) -> dict[str, float | int]:
        assertions = [assertion for scenario in scenarios for assertion in scenario["assertions"]]
        passed_assertions = [assertion for assertion in assertions if assertion.get("pass") is True]
        no_hit_assertions = [assertion for assertion in assertions if assertion.get("type") in {"abstention_reason", "abstention_any_of"}]
        provenance_assertions = [assertion for assertion in assertions if assertion.get("type") == "provenance_fields"]
        status_assertions = [assertion for assertion in assertions if assertion.get("type") == "status"]
        return {
            "scenario_pass_rate": _rate([scenario["passed"] for scenario in scenarios]),
            "assertion_pass_rate": _rate([assertion.get("pass") is True for assertion in assertions]),
            "empty_correct_rate": _rate([assertion.get("pass") is True for assertion in no_hit_assertions]),
            "false_positive_rate": 1.0 - _rate([assertion.get("pass") is True for assertion in no_hit_assertions]),
            "replace_supersession_rate": _rate([assertion.get("pass") is True for assertion in status_assertions]),
            "provenance_completeness": _rate([assertion.get("pass") is True for assertion in provenance_assertions]),
        }


def _rate(values: list[bool]) -> float:
    return sum(1 for value in values if value) / len(values) if values else 0.0


def run_quality_benchmark(dataset: QualityDataset, output_dir: Path) -> dict[str, Any]:
    """Run a Quality Benchmark with isolated storage."""
    runner = QualityRunner(dataset, output_dir)
    try:
        return runner.run()
    finally:
        runner.close()
```

- [ ] **Step 4: Run Quality runner test**

Run: `pytest tests/test_quality_benchmark.py -v`

Expected: PASS. The `ingest_with_fake_contradiction` scenarios use `AlwaysContradictsDetector` and must exercise the same SupersessionEngine path as Task 7.

- [ ] **Step 5: Add CLI quality mode test**

Append to `tests/test_benchmark_cli.py`:

```python

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
```

- [ ] **Step 6: Modify reports to write quality scenario CSV**

Modify `src/mnemlet/benchmark/reports.py`:

1. At the start of `_write_csv`, before `fields = [...]`, add:

```python
    if result.get("mode") == "quality":
        _write_quality_csv(result, path)
        return
```

2. Add this function after `_write_csv`:

```python
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
```

- [ ] **Step 7: Modify CLI to support quality mode**

Modify `src/mnemlet/__main__.py`:

1. Change benchmark modes loop:

```python
    for mode in ("quick", "full", "quality"):
```

2. In benchmark command handling, replace dataset/runner block with:

```python
        if args.benchmark_mode == "quality":
            from mnemlet.benchmark.datasets import load_quality_dataset
            from mnemlet.benchmark.quality import run_quality_benchmark

            dataset = load_quality_dataset(args.dataset, root=Path.cwd())
            result = run_quality_benchmark(dataset, output_dir=output_dir)
        else:
            from mnemlet.benchmark.datasets import load_dataset
            from mnemlet.benchmark.runner import run_retrieval_benchmark

            dataset = load_dataset(args.dataset, root=Path.cwd())
            result = run_retrieval_benchmark(
                dataset,
                output_dir=output_dir,
                limit=args.limit,
                min_score=args.min_score,
            )
```

3. Keep `run_id`, `mode`, `command`, `environment`, adapters, live checks, reports after that block. Guard live checks with `if args.benchmark_mode == "full":` as it already is.

- [ ] **Step 8: Run CLI quality test**

Run: `pytest tests/test_benchmark_cli.py::test_benchmark_quality_writes_reports -v`

Expected: PASS.

- [ ] **Step 9: Run benchmark regression tests**

Run: `pytest tests/test_quality_benchmark.py tests/test_benchmark_cli.py tests/test_benchmark_reports.py -v`

Expected: PASS.

- [ ] **Step 10: Commit Task 10 changes if commits are authorized**

Run:

```bash
git add src/mnemlet/__main__.py src/mnemlet/benchmark/quality.py src/mnemlet/benchmark/reports.py tests/test_benchmark_cli.py tests/test_quality_benchmark.py
git commit -m "feat: add quality benchmark runner"
```

Expected: commit succeeds if Christoph authorized commits. If not authorized, report `git status --short`.

---

## Task 11: Final verification and release-gate evidence

**Files:**
- Modify only files needed to fix failures revealed by verification.

- [ ] **Step 1: Run full pytest suite**

Run: `pytest -q`

Expected: all tests pass. Record the exact passed/warnings count.

- [ ] **Step 2: Run quick benchmark with adapters**

Run:

```bash
mnemlet benchmark quick --dataset public --output benchmark-results/latest --format json,md,csv --include-adapters
```

Expected:

- command exits `0`
- `benchmark-results/latest/results.json` exists
- summary contains `hit_at_3 >= 0.95`
- summary contains `adapter_success_rate = 1.0`

- [ ] **Step 3: Run quality benchmark**

Run:

```bash
mnemlet benchmark quality --dataset public --output benchmark-results/latest/quality --format json,md,csv
```

Expected:

- command exits `0`
- `benchmark-results/latest/quality/results.json` exists
- summary contains `empty_correct_rate >= 0.67`
- summary contains `provenance_completeness >= 0.95`
- summary contains OpenWebUI/OpenCode adapter success metrics

- [ ] **Step 4: Inspect git status**

Run: `git status --short --branch`

Expected: only intended files are modified/untracked. Benchmark result files should follow existing `.gitignore` behavior; if volatile reports appear, do not commit them.

- [ ] **Step 5: Commit final fixes if commits are authorized**

Run:

```bash
git add src tests benchmarks docs
git commit -m "test: verify memory intelligence quality gates"
```

Expected: commit succeeds if Christoph authorized commits and there are final verification/doc changes to commit. If not authorized or no changes remain, report status instead.

---

## Spec Coverage Map

| Spec requirement | Plan task |
|------------------|-----------|
| Additive schema fields and statuses | Task 1 |
| Legacy recall compatibility | Task 2, Task 11 |
| Provenance source/rank/status fields | Task 2, Task 6 |
| Minimal classifier | Task 3 |
| Minimal policy | Task 3 |
| Context Pack Builder | Task 4, Task 5 |
| Abstention / No-Hit | Task 4, Task 5, Task 8 |
| Review Commands | Task 6 |
| Manual replace supersession | Task 6 |
| Automatic Supersession with fake detector | Task 7 |
| OpenWebUI no restart/no network contract tests | Task 8 |
| OpenCode adapter contract | Task 8 |
| Quality Benchmark MVP dataset | Task 9 |
| Quality Benchmark runner and CLI | Task 10 |
| Release gates and final verification | Task 11 |

## Execution Notes

- Use a git worktree at execution time if Christoph wants isolation.
- Do not touch productive OpenWebUI services.
- Do not run live OpenWebUI chat requests.
- Keep `/api/v1/recall` and existing MCP tools compatible.
- Write failing tests first for each task.
- Commit only when Christoph explicitly authorizes commits for the execution run.
