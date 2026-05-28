"""Tests for extraction pipeline."""

from datetime import datetime
from mnemlet.intelligence.pipeline import ExtractionPipeline


class MockIngestEngine:
    def __init__(self, fail_first: bool = False):
        self.ingested = []
        self.fail_first = fail_first
        self._calls = 0

    def ingest(self, content, namespace, importance, metadata):
        self._calls += 1
        if self.fail_first and self._calls == 1:
            raise ValueError("simulated ingest failure")
        self.ingested.append({
            "content": content,
            "namespace": namespace,
            "importance": importance,
            "metadata": metadata,
        })


class MockLLM:
    def generate(self, prompt: str) -> str:
        if "extract" in prompt.lower():
            return '[{"content": "Test memory", "type": "fact", "importance": 0.8, "namespace": "test"}]'
        return "Test summary of conversation."


def _add_two(pipeline):
    pipeline.add_message(
        session_key="test-session",
        message={"role": "user", "content": "Hello", "timestamp": datetime.now()},
        platform="test",
        namespace="test",
    )
    pipeline.add_message(
        session_key="test-session",
        message={"role": "assistant", "content": "Hi!", "timestamp": datetime.now()},
        platform="test",
        namespace="test",
    )


def test_pipeline_extracts_and_ingests():
    ingest = MockIngestEngine()
    pipeline = ExtractionPipeline(
        ingest_engine=ingest,
        llm_client=MockLLM(),
        extract_memories=True,
        summarize_conversations=True,
    )

    _add_two(pipeline)
    pipeline.flush()

    # Should have ingested extracted memory + summary
    assert len(ingest.ingested) == 2
    assert ingest.ingested[0]["content"] == "Test memory"
    assert ingest.ingested[1]["content"] == "Test summary of conversation."
    assert ingest.ingested[0]["metadata"]["source"] == "extraction_pipeline"


def test_pipeline_summary_only_when_extraction_disabled():
    ingest = MockIngestEngine()
    pipeline = ExtractionPipeline(
        ingest_engine=ingest,
        llm_client=MockLLM(),
        extract_memories=False,
        summarize_conversations=True,
    )

    _add_two(pipeline)
    pipeline.flush()

    assert len(ingest.ingested) == 1
    assert ingest.ingested[0]["content"] == "Test summary of conversation."


def test_pipeline_survives_single_ingest_failure():
    ingest = MockIngestEngine(fail_first=True)
    pipeline = ExtractionPipeline(ingest_engine=ingest, llm_client=MockLLM())

    _add_two(pipeline)
    pipeline.flush()

    # First memory raised; the second (summary) still got ingested
    assert len(ingest.ingested) == 1
    assert ingest.ingested[0]["content"] == "Test summary of conversation."
