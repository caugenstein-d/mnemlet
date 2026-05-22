"""Recall pipeline: embed → hybrid search → filter → return."""

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


class RecallEngine:
    """Handles memory retrieval with hybrid search."""

    def __init__(self, db, chroma, embedder, decay_engine=None):
        self.db = db
        self.chroma = chroma
        self.embedder = embedder
        self.decay_engine = decay_engine

    def recall(
        self,
        query: str,
        namespace: Optional[str] = None,
        limit: int = DEFAULT_TOP_N,
        min_score: float = 0.0,
        include_statuses: set[str] | None = None,
    ) -> list[dict]:
        """Recall memories relevant to the query."""
        limit = min(limit, MAX_TOP_N)
        candidate_limit = max(limit * 4, MAX_TOP_N * 2)
        statuses = include_statuses if include_statuses is not None else {MEMORY_STATUS_ACTIVE}

        vector_results = self._vector_search(query, namespace, candidate_limit)
        fts_results = self._fts_search(query, namespace, candidate_limit)

        merged = self._merge_results(vector_results, fts_results, candidate_limit)
        enriched = self._attach_memory_rows(merged, statuses)
        filtered = [m for m in enriched if m["score"] >= min_score]
        for index, item in enumerate(filtered, start=1):
            item["rank"] = index

        # Enforce recall token budget
        total_tokens = 0
        budgeted = []
        for m in filtered:
            tokens = self.embedder.count_tokens(m["content"])
            if total_tokens + tokens <= MAX_RECALL_TOKENS:
                budgeted.append(m)
                total_tokens += tokens
            else:
                break  # Stop adding — budget exhausted

        filtered = budgeted

        for m in filtered:
            self.db.record_interaction(m["id"], "recall", agent_id="api")
            if self.decay_engine:
                self.decay_engine.boost_memory(m["id"], "recall", agent_id="api")

        return filtered[:limit]

    def _vector_search(self, query: str, namespace: Optional[str], limit: int) -> list[dict]:
        """Vector similarity search via ChromaDB."""
        where = {"namespace": namespace} if namespace else None
        result = self.chroma.query(query_text=query, n_results=limit, where=where)

        items = []
        if result["ids"] and result["ids"][0]:
            for i, doc_id in enumerate(result["ids"][0]):
                dist = result.get("distances", [[]])[0]
                score = 1.0 - dist[i] if dist else 0.5
                doc = result["documents"][0][i] if result["documents"] else ""
                meta = result["metadatas"][0][i] if result["metadatas"] else {}
                items.append({
                    "id": doc_id,
                    "content": doc,
                    "score": score,
                    "namespace": meta.get("namespace", ""),
                    "source": "vector",
                })

        return items

    def _fts_search(self, query: str, namespace: Optional[str], limit: int) -> list[dict]:
        """Full-text search via SQLite FTS5."""
        try:
            results = self.db.search_fts(query, namespace, limit)
            return [
                {
                    "id": r["id"],
                    "content": r["content_preview"],
                    "score": 0.5,
                    "namespace": r["namespace"],
                    "source": "fts",
                }
                for r in results
            ]
        except Exception:
            return []

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
