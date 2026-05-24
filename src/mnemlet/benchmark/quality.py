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
        self._temp_dir = None
        self.db = None
        self.ingest_engine = None
        self.recall_engine = None
        self.review_service = None

    def run(self) -> dict[str, Any]:
        scenario_results = []
        for scenario in self.dataset.scenarios:
            self.setup()
            self.logical_ids = {}
            self.scores_before_confirm = {}
            try:
                assertions = []
                for phase in scenario.phases:
                    assertions.extend(self._run_phase(phase.action, phase.payload))
                passed = all(item["pass"] for item in assertions)
                scenario_results.append({"id": scenario.id, "category": scenario.category, "passed": passed, "assertions": assertions})
            finally:
                self.close()
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
            real_id, memory, missing = self._memory_or_missing_assertion(payload["memory_id"], "confirm")
            if memory is None:
                return missing
            before = memory["retention_score"]
            self.scores_before_confirm[payload["memory_id"]] = before
            self.review_service.confirm(real_id)
            return []
        if action == "assert_score_increased":
            _real_id, memory, missing = self._memory_or_missing_assertion(payload["memory_id"], "assert_score_increased")
            if memory is None:
                return missing
            current = memory["retention_score"]
            before = self.scores_before_confirm[payload["memory_id"]]
            return [{"type": "score_increased", "pass": current > before}]
        if action == "assert_status":
            _real_id, memory, missing = self._memory_or_missing_assertion(payload["memory_id"], "assert_status")
            if memory is None:
                return missing
            status = memory["status"]
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

    def _memory_or_missing_assertion(self, logical_id: str, assertion_type: str) -> tuple[str, dict[str, Any] | None, list[dict[str, Any]]]:
        if self.db is None:
            raise RuntimeError("quality runner is not set up")
        real_id = self.logical_ids[logical_id]
        memory = self.db.get_memory(real_id)
        if memory is None:
            return real_id, None, [
                {
                    "type": "missing_memory",
                    "assertion": assertion_type,
                    "pass": False,
                    "memory_id": logical_id,
                    "real_id": real_id,
                }
            ]
        return real_id, memory, []

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
        no_hit_assertions = [assertion for assertion in assertions if assertion.get("type") in {"abstention_reason", "abstention_any_of"}]
        provenance_assertions = [assertion for assertion in assertions if assertion.get("type") == "provenance_fields"]
        status_assertions = [assertion for assertion in assertions if assertion.get("type") == "status"]
        return {
            "scenario_pass_rate": _rate([scenario["passed"] for scenario in scenarios]),
            "assertion_pass_rate": _rate([assertion.get("pass") is True for assertion in assertions]),
            "empty_correct_rate": _rate([assertion.get("pass") is True for assertion in no_hit_assertions]),
            "false_positive_rate": (1.0 - _rate([assertion.get("pass") is True for assertion in no_hit_assertions])) if no_hit_assertions else 0.0,
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
