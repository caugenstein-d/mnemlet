"""Recall pipeline: embed → hybrid search → filter → return."""

from typing import Optional
from memoria.constants import DEFAULT_TOP_N, MAX_TOP_N, HYBRID_BM25_WEIGHT, HYBRID_VECTOR_WEIGHT


class RecallEngine:
    """Handles memory retrieval with hybrid search."""

    def __init__(self, db, chroma, embedder):
        self.db = db
        self.chroma = chroma
        self.embedder = embedder

    def recall(
        self,
        query: str,
        namespace: Optional[str] = None,
        limit: int = DEFAULT_TOP_N,
        min_score: float = 0.0,
    ) -> list[dict]:
        """Recall memories relevant to the query."""
        limit = min(limit, MAX_TOP_N)

        vector_results = self._vector_search(query, namespace, limit * 2)
        fts_results = self._fts_search(query, namespace, limit * 2)

        merged = self._merge_results(vector_results, fts_results, limit)
        filtered = [m for m in merged if m["score"] >= min_score]

        for m in filtered:
            self.db.record_interaction(m["id"], "recall", agent_id="api")

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
        """Merge vector and FTS results, weighted, deduplicated."""
        scored = {}

        for item in vector:
            sid = item["id"]
            scored[sid] = scored.get(sid, {"id": sid, "content": item["content"],
                "namespace": item["namespace"], "score": 0.0})
            scored[sid]["score"] += HYBRID_VECTOR_WEIGHT * item["score"]

        for item in fts:
            sid = item["id"]
            scored[sid] = scored.get(sid, {"id": sid, "content": item["content"],
                "namespace": item["namespace"], "score": 0.0})
            scored[sid]["score"] += HYBRID_BM25_WEIGHT * item["score"]

        return sorted(scored.values(), key=lambda x: x["score"], reverse=True)[:limit]
