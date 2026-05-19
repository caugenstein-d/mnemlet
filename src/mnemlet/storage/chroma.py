"""ChromaDB vector storage client."""

from pathlib import Path
from typing import Optional
import chromadb
from chromadb.api.types import EmbeddingFunction, Embeddings
from chromadb.config import Settings as ChromaSettings


class _MnemletEmbeddingFn(EmbeddingFunction):
    """ChromaDB-compatible embedding function wrapping MnemletEmbedding."""

    def __init__(self, embedder):
        self.embedder = embedder

    def __call__(self, input: list[str]) -> Embeddings:
        return self.embedder.embed_batch(input)


class MnemletChroma:
    """ChromaDB client for vector storage and retrieval."""

    def __init__(self, persist_dir: Path, embedder):
        persist_dir.mkdir(parents=True, exist_ok=True)
        self.client = chromadb.PersistentClient(
            path=str(persist_dir),
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        self._embedding_fn = _MnemletEmbeddingFn(embedder)
        self._collection = None

    @property
    def collection(self):
        """Lazy-load or create the collection."""
        if self._collection is None:
            collection_name = "mnemlet_memories"
            try:
                self._collection = self.client.get_collection(
                    name=collection_name,
                    embedding_function=self._embedding_fn,
                )
            except Exception:
                self._collection = self.client.create_collection(
                    name=collection_name,
                    embedding_function=self._embedding_fn,
                    metadata={"hnsw:space": "cosine"},
                )
        return self._collection

    def add(self, doc_id: str, text: str, metadata: Optional[dict] = None) -> None:
        """Add a document to the collection."""
        self.collection.add(
            ids=[doc_id],
            documents=[text],
            metadatas=[metadata] if metadata else None,
        )

    def query(self, query_text: str, n_results: int = 5, where: Optional[dict] = None) -> dict:
        """Query the collection for similar documents."""
        return self.collection.query(
            query_texts=[query_text],
            n_results=n_results,
            where=where,
        )

    def delete(self, doc_id: str) -> None:
        """Delete a document by ID."""
        self.collection.delete(ids=[doc_id])

    def count(self) -> int:
        """Return the number of documents in the collection."""
        return self.collection.count()
