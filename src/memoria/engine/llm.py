"""LLM Backend — optional local LLM via Ollama for enhanced sleep tasks."""

import json
from typing import Optional
import httpx


class LLMBackend:
    """Abstraction for local LLM inference (Ollama)."""

    def __init__(self, base_url: str = "http://localhost:11434", model: str = "gemma4-e2b:q4_0"):
        self.base_url = base_url.rstrip("/")
        self.model = model
        self._client = None

    @property
    def client(self):
        if self._client is None:
            self._client = httpx.Client(timeout=120.0)
        return self._client

    @property
    def available(self) -> bool:
        """Check if the LLM backend is reachable."""
        try:
            resp = self.client.get(f"{self.base_url}/api/tags", timeout=5.0)
            return resp.status_code == 200
        except Exception:
            return False

    def generate(self, prompt: str, system: str = "",
                 temperature: float = 0.3, max_tokens: int = 4096) -> str:
        """Generate a completion from the local LLM."""
        messages = []
        if system:
            messages.append({"role": "system", "content": system})
        messages.append({"role": "user", "content": prompt})

        resp = self.client.post(
            f"{self.base_url}/api/chat",
            json={
                "model": self.model,
                "messages": messages,
                "stream": False,
                "options": {
                    "temperature": temperature,
                    "num_predict": max_tokens,
                },
            },
        )
        resp.raise_for_status()
        data = resp.json()
        return data.get("message", {}).get("content", "")

    def summarize_memories(self, memories: list[str]) -> str:
        """Summarize a list of memory contents."""
        prompt = "Summarize these related memories in 2-3 sentences:\n\n"
        for i, mem in enumerate(memories, 1):
            prompt += f"{i}. {mem}\n"
        return self.generate(prompt, system="You are a memory consolidation assistant. Be concise and factual.")

    def detect_contradiction(self, fact_a: str, fact_b: str) -> dict:
        """Check if two facts contradict each other."""
        prompt = f"""Compare these two facts and determine if they contradict each other.
Respond in JSON format: {{"contradiction": true/false, "explanation": "..."}}

Fact A: {fact_a}
Fact B: {fact_b}"""
        result = self.generate(prompt, system="You are a fact-checking assistant. Respond only in valid JSON.")
        try:
            return json.loads(result)
        except json.JSONDecodeError:
            return {"contradiction": False, "explanation": "parse error"}

    def close(self):
        if self._client:
            self._client.close()
            self._client = None
