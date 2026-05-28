"""End-to-end extraction: raw platform payload → adapter → pipeline → ingest.

Exercises the full Phase 1 chain for every supported platform using a mock
LLM and a mock ingest engine (no Ollama required).
"""

from mnemlet.intelligence.adapters import get_adapter
from mnemlet.intelligence.pipeline import ExtractionPipeline


class MockIngestEngine:
    def __init__(self):
        self.ingested = []

    def ingest(self, content, namespace, importance, metadata):
        self.ingested.append(
            {"content": content, "namespace": namespace, "importance": importance, "metadata": metadata}
        )


class MockLLM:
    def generate(self, prompt: str) -> str:
        if "extract" in prompt.lower():
            return '[{"content": "extracted fact", "type": "fact", "importance": 0.8}]'
        return "A short conversation summary."


# One representative raw payload per Phase 1 platform.
PLATFORM_PAYLOADS = {
    "openwebui": {
        "chat_id": "ow-1",
        "namespace": "openwebui/christoph",
        "messages": [
            {"role": "user", "content": "I prefer dark mode", "timestamp": 1716883200},
            {"role": "assistant", "content": "Noted.", "timestamp": 1716883201},
        ],
    },
    "claude_code": {
        "session_id": "cc-1",
        "project": "mnemlet",
        "messages": [
            {"role": "user", "content": "Refactor the buffer", "timestamp": "2026-05-28T10:00:00Z"},
            {"role": "assistant", "content": "Done.", "timestamp": 1716883201},
        ],
    },
    "opencode": {
        "session_id": "oc-1",
        "messages": [{"role": "user", "content": "Run the tests", "timestamp": 1716883200}],
    },
    "openclaw": {
        "session_id": "ocl-1",
        "messages": [{"role": "user", "content": "Summarize the repo", "timestamp": 1716883200}],
    },
    "cursor": {
        "conversation_id": "cur-1",
        "messages": [
            {"role": "user", "content": "Fix bug", "timestamp": "2026-05-28T10:00:00Z", "context": {"files": ["a.py"]}},
        ],
    },
    "claude_desktop": {
        "conversation_id": "cd-1",
        "project": "mnemlet",
        "messages": [{"role": "user", "content": "Plan v0.4", "timestamp": 1716883200}],
    },
    "generic": {
        "id": "gen-1",
        "namespace": "custom/ns",
        "messages": [{"role": "user", "content": "hello world"}],
    },
}


def _run_platform(platform: str, raw: dict):
    conv = get_adapter(platform).normalize(raw)
    ingest = MockIngestEngine()
    pipeline = ExtractionPipeline(ingest_engine=ingest, llm_client=MockLLM())
    for msg in conv.messages:
        pipeline.add_message(
            session_key=conv.session_id or "s",
            message=msg,
            platform=conv.platform,
            namespace=conv.namespace,
        )
    pipeline.flush()
    return conv, ingest


def test_all_phase1_platforms_extract_and_ingest():
    for platform, raw in PLATFORM_PAYLOADS.items():
        conv, ingest = _run_platform(platform, raw)

        # 1 extracted memory + 1 summary per conversation
        assert len(ingest.ingested) == 2, f"{platform}: expected 2 ingested"
        contents = [m["content"] for m in ingest.ingested]
        assert "extracted fact" in contents
        assert "A short conversation summary." in contents

        # provenance carries the right platform; summary keeps the conv namespace
        for m in ingest.ingested:
            assert m["metadata"]["platform"] == conv.platform
            assert m["metadata"]["source"] == "extraction_pipeline"


def test_namespace_routing_for_named_platforms():
    _, ow = _run_platform("openwebui", PLATFORM_PAYLOADS["openwebui"])
    # summary memory uses the conversation namespace
    summary = [m for m in ow.ingested if m["content"] == "A short conversation summary."][0]
    assert summary["namespace"] == "openwebui/christoph"

    _, cd = _run_platform("claude_desktop", PLATFORM_PAYLOADS["claude_desktop"])
    summary = [m for m in cd.ingested if m["content"] == "A short conversation summary."][0]
    assert summary["namespace"] == "claude_desktop/mnemlet"
