"""Isolated benchmark runner for retrieval evaluation."""

from __future__ import annotations

import shutil
import tempfile
from pathlib import Path
from time import perf_counter
from typing import Any

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
    """Run a benchmark dataset against isolated temporary Mnémlet storage."""

    def __init__(
        self,
        dataset: BenchmarkDataset,
        output_dir: Path,
        limit: int = 5,
        min_score: float = 0.1,
    ) -> None:
        self.dataset = dataset
        self.output_dir = output_dir
        self.limit = limit
        self.min_score = min_score
        self.memory_id_map: dict[str, str] = {}
        self.reverse_memory_id_map: dict[str, str] = {}
        self.config: MnemletConfig | None = None
        self._temp_dir: Path | None = None
        self._db: MnemletDB | None = None
        self._chroma: MnemletChroma | None = None
        self._embedder: MnemletEmbedding | None = None
        self._vault: VaultWriter | None = None
        self._ingest_engine: IngestEngine | None = None
        self._recall_engine: RecallEngine | None = None

    def setup(self) -> None:
        """Create isolated storage and ingest all benchmark memories."""
        if self._ingest_engine is not None:
            return

        self.output_dir.mkdir(parents=True, exist_ok=True)
        self._temp_dir = Path(
            tempfile.mkdtemp(prefix="mnemlet-benchmark-", dir=self.output_dir)
        )
        self.config = MnemletConfig(
            data_dir=self._temp_dir / "data",
            sqlite_path=self._temp_dir / "data" / "mnemlet.db",
            chroma_path=self._temp_dir / "data" / "chroma",
            vault_path=self._temp_dir / "data" / "vault",
        )

        self._db = MnemletDB(self.config.sqlite_path)
        self._embedder = MnemletEmbedding()
        self._chroma = MnemletChroma(self.config.chroma_path, self._embedder)
        self._vault = VaultWriter(self.config.vault_path)
        self._ingest_engine = IngestEngine(
            db=self._db,
            chroma=self._chroma,
            embedder=self._embedder,
            vault=self._vault,
        )
        self._recall_engine = RecallEngine(
            db=self._db,
            chroma=self._chroma,
            embedder=self._embedder,
        )

        for case in self.dataset.cases:
            for memory in case.memories:
                result = self._ingest_engine.ingest(
                    content=memory.content,
                    namespace=memory.namespace,
                    importance=memory.importance,
                    metadata={
                        "benchmark_logical_id": memory.id,
                        "benchmark_case_id": case.id,
                        "benchmark_category": case.category,
                        "tags": memory.tags,
                    },
                )
                real_id = str(result["memory_id"])
                self.memory_id_map[memory.id] = real_id
                self.reverse_memory_id_map[real_id] = memory.id
                if memory.status != "active":
                    self._update_memory_status(real_id, memory.status)

    def close(self) -> None:
        """Close database handles and remove temporary benchmark storage."""
        if self._db is not None:
            self._db.close()
        self._db = None
        self._chroma = None
        self._embedder = None
        self._vault = None
        self._ingest_engine = None
        self._recall_engine = None
        if self._temp_dir is not None:
            shutil.rmtree(self._temp_dir, ignore_errors=True)
        self._temp_dir = None

    def run(self) -> dict[str, Any]:
        """Execute all benchmark queries and return detailed retrieval results."""
        self.setup()
        if self.config is None or self._recall_engine is None:
            raise RuntimeError("benchmark runner setup failed")

        query_results: list[dict[str, Any]] = []
        for case in self.dataset.cases:
            for query in case.queries:
                start = perf_counter()
                recalled = self._recall_engine.recall(
                    query=query.query,
                    namespace=query.namespace,
                    limit=self.limit,
                    min_score=self.min_score,
                )
                latency_ms = (perf_counter() - start) * 1000
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

    def _update_memory_status(self, memory_id: str, status: str) -> None:
        if self._db is None:
            raise RuntimeError("benchmark runner is not set up")
        self._db.conn.execute(
            "UPDATE memories SET status = ? WHERE id = ?",
            (status, memory_id),
        )
        self._db.conn.commit()

    def _format_result(self, item: dict[str, Any]) -> dict[str, Any]:
        memory_id = str(item["id"])
        return {
            "memory_id": memory_id,
            "logical_id": self.reverse_memory_id_map.get(memory_id),
            "namespace": item.get("namespace"),
            "score": item.get("score", 0.0),
            "content": item.get("content", ""),
        }


def run_retrieval_benchmark(
    dataset: BenchmarkDataset,
    output_dir: Path,
    limit: int = 5,
    min_score: float = 0.1,
) -> dict[str, Any]:
    """Run a retrieval benchmark with isolated storage and clean it up afterward."""
    runner = BenchmarkRunner(
        dataset=dataset,
        output_dir=output_dir,
        limit=limit,
        min_score=min_score,
    )
    try:
        return runner.run()
    finally:
        runner.close()
