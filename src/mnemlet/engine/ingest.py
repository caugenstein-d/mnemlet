"""Ingest pipeline: chunk → embed → dedup → store."""

import hashlib
from typing import Optional
from mnemlet.constants import MAX_CHUNK_TOKENS, DEDUP_THRESHOLD
from mnemlet.intelligence.classifier import classify_memory


class IngestEngine:
    """Handles memory ingestion: chunking, dedup, and storage."""

    def __init__(self, db, chroma, embedder, vault=None):
        self.db = db
        self.chroma = chroma
        self.embedder = embedder
        self.vault = vault

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
        """Ingest a memory: chunk, dedup, embed, store. Return result."""
        chunks = self._chunk(content)

        results = []
        for i, chunk in enumerate(chunks):
            memory_id = self._content_id(chunk, namespace)
            content_hash = hashlib.sha256(chunk.encode()).hexdigest()

            if dedup and i == 0 and len(chunks) == 1 and self._is_duplicate(chunk, namespace):
                existing = self.db.get_memory(memory_id)
                if existing:
                    return {
                        "memory_id": existing["id"],
                        "stored": False,
                        "dedup": True,
                        "namespace": namespace,
                        "retention_score": existing["retention_score"],
                        "chunk_count": 1,
                    }

            db_result = self.db.insert_memory(
                memory_id=memory_id,
                namespace=namespace,
                content_preview=chunk[:200],
                content_hash=content_hash,
                importance=importance,
                metadata=metadata,
            )
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

            self.chroma.add(
                doc_id=memory_id,
                text=chunk,
                metadata={
                    "namespace": namespace,
                    "retention_score": db_result["retention_score"],
                    "created_at": db_result["created_at"],
                },
            )

            # Write to vault
            if self.vault:
                self.vault.write_memory(
                    memory_id=memory_id,
                    namespace=namespace,
                    content=chunk,
                    retention_score=db_result["retention_score"],
                    importance=importance,
                    created_at=db_result["created_at"],
                    metadata=metadata,
                )

            results.append(memory_id)

        return {
            "memory_id": results[0] if len(results) == 1 else results,
            "stored": True,
            "dedup": False,
            "namespace": namespace,
            "retention_score": importance * 0.5,
            "chunk_count": len(results),
        }

    def _chunk(self, content: str, max_tokens: int = MAX_CHUNK_TOKENS) -> list[str]:
        """Split content into chunks respecting token limits."""
        token_count = self.embedder.count_tokens(content)
        if token_count <= max_tokens:
            return [content]

        paragraphs = content.split("\n\n")
        chunks = []
        current = ""

        for para in paragraphs:
            if self.embedder.count_tokens(current + para) <= max_tokens:
                current = (current + "\n\n" + para).strip()
            else:
                if current:
                    chunks.append(current)
                if self.embedder.count_tokens(para) > max_tokens:
                    sentences = para.replace(". ", ".|").split("|")
                    sub = ""
                    for s in sentences:
                        if self.embedder.count_tokens(sub + s) <= max_tokens:
                            sub = (sub + " " + s).strip()
                        else:
                            if sub:
                                chunks.append(sub)
                            sub = s
                    if sub:
                        chunks.append(sub)
                else:
                    current = para

        if current:
            chunks.append(current)

        return [c for c in chunks if c.strip()]

    def _content_id(self, content: str, namespace: str) -> str:
        """Generate deterministic ID from content + namespace."""
        combined = f"{namespace}:{content}"
        return hashlib.sha256(combined.encode()).hexdigest()[:32]

    def _is_duplicate(self, content: str, namespace: str) -> bool:
        """Check if similar content already exists in namespace."""
        embedding = self.embedder.embed(content)
        results = self.chroma.query(
            query_text=content,
            n_results=1,
            where={"namespace": namespace},
        )
        if results["ids"] and results["ids"][0]:
            existing_id = results["ids"][0][0]
            existing = self.db.get_memory(existing_id)
            if existing:
                existing_embedding = self.embedder.embed(existing["content_preview"])
                sim = self.embedder.cosine_similarity(embedding, existing_embedding)
                return sim > DEDUP_THRESHOLD
        return False
