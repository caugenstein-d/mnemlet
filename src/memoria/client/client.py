"""MemoriaClient — Python SDK for the Memoria Memory Engine."""

from typing import Optional
import httpx


class MemoriaClient:
    """Client for the Memoria Memory Engine REST API."""

    def __init__(self, base_url: str = "http://localhost:4050"):
        self.base_url = base_url.rstrip("/")
        self._client = None

    @property
    def client(self) -> httpx.Client:
        if self._client is None:
            self._client = httpx.Client(timeout=30.0)
        return self._client

    def _post(self, path: str, json: dict) -> dict:
        resp = self.client.post(f"{self.base_url}{path}", json=json)
        resp.raise_for_status()
        return resp.json()

    def _get(self, path: str) -> dict:
        resp = self.client.get(f"{self.base_url}{path}")
        resp.raise_for_status()
        return resp.json()

    def ingest(
        self,
        content: str,
        namespace: str = "default",
        importance: float = 0.5,
        metadata: Optional[dict] = None,
    ) -> dict:
        """Store a memory."""
        return self._post("/api/v1/ingest", {
            "content": content,
            "namespace": namespace,
            "importance": importance,
            "metadata": metadata or {},
        })

    def recall(
        self,
        query: str,
        namespace: Optional[str] = None,
        limit: int = 5,
        min_score: float = 0.0,
    ) -> dict:
        """Retrieve relevant memories."""
        return self._post("/api/v1/recall", {
            "query": query,
            "namespace": namespace,
            "limit": limit,
            "min_score": min_score,
        })

    def status(self) -> dict:
        """Get system status."""
        return self._get("/api/v1/status")

    def health(self) -> dict:
        """Health check."""
        return self._get("/api/v1/health")

    def run_decay(
        self,
        limit: int = 500,
        purge_threshold: float = 0.05,
        dry_run: bool = False,
    ) -> dict:
        """Manually trigger decay + purge."""
        return self._post("/api/v1/decay/run", {
            "limit": limit,
            "purge_threshold": purge_threshold,
            "dry_run": dry_run,
        })

    def get_decay_config(self, namespace: str) -> dict:
        """Get decay config for a namespace."""
        return self._get(f"/api/v1/namespaces/{namespace}/decay")

    def set_decay_config(
        self,
        namespace: str,
        lambda_: float = 0.01,
        purge_threshold: float = 0.05,
    ) -> dict:
        """Set decay config for a namespace."""
        return httpx.put(
            f"{self.base_url}/api/v1/namespaces/{namespace}/decay",
            json={"lambda": lambda_, "purge_threshold": purge_threshold},
        ).json()

    def close(self):
        """Close the HTTP client."""
        if self._client:
            self._client.close()
            self._client = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()
        return False
