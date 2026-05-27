"""Ingest pipeline: chunk → embed → dedup → store."""

import hashlib
import uuid
from typing import Optional
from mnemlet.constants import MAX_CHUNK_TOKENS, DEDUP_THRESHOLD, MEMORY_TYPES
from mnemlet.intelligence.classifier import classify_memory
from mnemlet.security.audit import AuditEvent
from mnemlet.security.namespace_policies import policy_value_bool
from mnemlet.security.secret_guard import SecretGuard


class IngestEngine:
    """Handles memory ingestion: chunking, dedup, and storage."""

    def __init__(self, db, chroma, embedder, vault=None, supersession_engine=None):
        self.db = db
        self.chroma = chroma
        self.embedder = embedder
        self.vault = vault
        self.supersession_engine = supersession_engine

    def ingest(
        self,
        content: str,
        namespace: str = "default",
        importance: float = 0.5,
        metadata: Optional[dict] = None,
        dedup: bool = True,
        memory_type: str | None = None,
        type_source: str | None = None,
        secret_guard_action: str = "block",
        caller: str = "api",
        caller_identity: str | None = None,
    ) -> dict:
        """Ingest a memory: chunk, dedup, embed, store. Return result."""
        if memory_type is not None and memory_type not in MEMORY_TYPES:
            raise ValueError(f"invalid memory type: {memory_type}")

        allow_ingest = policy_value_bool(self.db.get_namespace_policy(namespace, "allow_ingest"))
        secret_guard_action = self.db.get_namespace_policy(namespace, "secret_guard_action")
        guard_result = SecretGuard().enforce(content, secret_guard_action)  # type: ignore[arg-type]
        if guard_result.blocked:
            patterns = sorted({finding.pattern_type for finding in guard_result.findings})
            raise ValueError(f"secret_guard_blocked: patterns={','.join(patterns)}")
        if not guard_result.clean and guard_result.action == "warn":
            metadata = dict(metadata or {})
            metadata["secret_guard_result"] = "warning"
            metadata["secret_guard_patterns"] = sorted(
                {finding.pattern_type for finding in guard_result.findings}
            )
        if guard_result.action == "allow":
            secret_guard_result = "allow"
        elif not guard_result.clean and guard_result.action == "warn":
            secret_guard_result = "warning"
        else:
            secret_guard_result = "clean"

        if not allow_ingest:
            self.db.record_audit(
                AuditEvent(
                    action="ingest",
                    namespace=namespace,
                    caller=caller,
                    caller_identity=caller_identity,
                    result="warning",
                    details={"policy": "allow_ingest"},
                )
            )
        elif secret_guard_result == "warning":
            self.db.record_audit(
                AuditEvent(
                    action="ingest",
                    namespace=namespace,
                    caller=caller,
                    caller_identity=caller_identity,
                    result="warning",
                    details={"policy": "secret_guard_action"},
                )
            )

        chunks = self._chunk(content)

        results = []
        all_superseded_ids: list[str] = []
        for i, chunk in enumerate(chunks):
            if dedup:
                memory_id = self._content_id(chunk, namespace)
            else:
                memory_id = uuid.uuid4().hex[:32]
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
                        "superseded_ids": [],
                        "contradiction_detected": False,
                    }

            db_result = self.db.insert_memory(
                memory_id=memory_id,
                namespace=namespace,
                content_preview=chunk[:200],
                content_hash=content_hash,
                importance=importance,
                metadata=metadata,
            )
            self.db.update_memory_trust(
                memory_id,
                ingested_by=caller,
                caller_identity=caller_identity,
                secret_guard_result=secret_guard_result,
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

            superseded_ids: list[str] = []
            if self.supersession_engine is not None:
                superseded_ids = self.supersession_engine.process_new_memory(db_result, chunk)
                if superseded_ids:
                    db_result = self.db.get_memory(memory_id) or db_result
                all_superseded_ids.extend(superseded_ids)

            results.append(memory_id)

        return {
            "memory_id": results[0] if len(results) == 1 else results,
            "stored": True,
            "dedup": False,
            "namespace": namespace,
            "retention_score": importance * 0.5,
            "chunk_count": len(results),
            "superseded_ids": all_superseded_ids,
            "contradiction_detected": bool(all_superseded_ids),
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
