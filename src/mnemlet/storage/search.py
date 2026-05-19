"""Search Backend — optional web search via SearXNG."""

from typing import Optional
import httpx


class SearchBackend:
    """Abstraction for web search (SearXNG self-hosted)."""

    def __init__(self, base_url: str = "http://localhost:8888"):
        self.base_url = base_url.rstrip("/")
        self._client = None

    @property
    def client(self):
        if self._client is None:
            self._client = httpx.Client(timeout=30.0)
        return self._client

    @property
    def available(self) -> bool:
        """Check if the search backend is reachable."""
        try:
            resp = self.client.get(f"{self.base_url}/health", timeout=5.0)
            return resp.status_code == 200
        except Exception:
            return False

    def search(self, query: str, max_results: int = 5) -> list[dict]:
        """Perform a web search via SearXNG.

        Returns list of {title, url, snippet}.
        """
        resp = self.client.get(
            f"{self.base_url}/search",
            params={"q": query, "format": "json", "categories": "general"},
        )
        resp.raise_for_status()
        data = resp.json()
        results = data.get("results", [])[:max_results]
        return [
            {"title": r.get("title", ""), "url": r.get("url", ""),
             "snippet": r.get("content", "")[:500]}
            for r in results
        ]

    def enrich_memory(self, memory_content: str, max_results: int = 3) -> Optional[str]:
        """Search the web and return enriched context for a memory."""
        results = self.search(memory_content, max_results=max_results)
        if not results:
            return None

        lines = ["## Web Context", ""]
        for r in results:
            lines.append(f"- **{r['title']}** — {r['snippet'][:200]}")
            lines.append(f"  {r['url']}")
            lines.append("")

        return "\n".join(lines)

    def close(self):
        if self._client:
            self._client.close()
            self._client = None
