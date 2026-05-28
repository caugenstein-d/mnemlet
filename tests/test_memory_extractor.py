"""Tests for memory extractor."""

from datetime import datetime
from mnemlet.intelligence.extractor import MemoryExtractor
from mnemlet.intelligence.conversation import Conversation, Message


class MockLLM:
    """Mock LLM for testing."""

    def __init__(self, response: str):
        self.response = response

    def generate(self, prompt: str) -> str:
        return self.response


def _conv():
    return Conversation(
        messages=[
            Message(role="user", content="I prefer dark mode", timestamp=datetime.now()),
            Message(role="assistant", content="Got it!", timestamp=datetime.now()),
        ],
        platform="test",
    )


def test_extractor_parses_valid_response():
    llm = MockLLM("""
    [
      {"content": "Christoph prefers dark mode", "type": "preference", "importance": 0.9, "namespace": "preferences"},
      {"content": "Christoph works on Mnémlet", "type": "fact", "importance": 0.8, "namespace": "projects/mnemlet"}
    ]
    """)

    extractor = MemoryExtractor(llm)
    memories = extractor.extract(_conv())

    assert len(memories) == 2
    assert memories[0]["content"] == "Christoph prefers dark mode"
    assert memories[0]["type"] == "preference"
    assert memories[0]["importance"] == 0.9


def test_extractor_handles_empty_response():
    extractor = MemoryExtractor(MockLLM("[]"))
    memories = extractor.extract(_conv())
    assert len(memories) == 0


def test_extractor_handles_invalid_json():
    extractor = MemoryExtractor(MockLLM("No memories found."))
    memories = extractor.extract(_conv())
    assert len(memories) == 0


def test_extractor_clamps_importance_and_defaults_namespace():
    llm = MockLLM('[{"content": "huge importance", "importance": 5, "type": "weird"}]')
    conv = Conversation(messages=[Message(role="user", content="x")], platform="t", namespace="ns/fallback")
    memories = MemoryExtractor(llm).extract(conv)
    assert len(memories) == 1
    assert memories[0]["importance"] == 1.0  # clamped to [0, 1]
    assert memories[0]["type"] == "context"  # invalid type → default
    assert memories[0]["namespace"] == "ns/fallback"  # missing → conversation namespace


def test_extractor_skips_blank_and_non_dict_entries():
    llm = MockLLM('[{"content": "  "}, "not-a-dict", {"content": "keep me"}]')
    memories = MemoryExtractor(llm).extract(_conv())
    assert len(memories) == 1
    assert memories[0]["content"] == "keep me"


def test_extractor_skips_llm_when_no_messages():
    class BoomLLM:
        def generate(self, prompt):
            raise AssertionError("LLM should not be called for empty conversations")

    memories = MemoryExtractor(BoomLLM()).extract(Conversation(messages=[], platform="t"))
    assert memories == []
