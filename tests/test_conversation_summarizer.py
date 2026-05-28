"""Tests for conversation summarizer."""

from datetime import datetime
from mnemlet.intelligence.summarizer import ConversationSummarizer
from mnemlet.intelligence.conversation import Conversation, Message


class MockLLM:
    def __init__(self, response: str):
        self.response = response

    def generate(self, prompt: str) -> str:
        return self.response


def test_summarizer_generates_summary():
    llm = MockLLM("Christoph discussed Mnémlet v0.4 planning. Decided to use LLM for extraction.")
    summarizer = ConversationSummarizer(llm)

    conv = Conversation(
        messages=[
            Message(role="user", content="Let's plan v0.4", timestamp=datetime.now()),
            Message(role="assistant", content="Sure, what features?", timestamp=datetime.now()),
        ],
        platform="test",
        namespace="projects/mnemlet",
    )

    result = summarizer.summarize(conv)

    assert "content" in result
    assert "Mnémlet v0.4" in result["content"]
    assert result["namespace"] == "projects/mnemlet"


def test_summarizer_returns_none_for_empty_conversation():
    summarizer = ConversationSummarizer(MockLLM("ignored"))
    assert summarizer.summarize(Conversation(messages=[], platform="test")) is None


def test_summarizer_returns_none_for_blank_output():
    summarizer = ConversationSummarizer(MockLLM("   "))
    conv = Conversation(messages=[Message(role="user", content="hi")], platform="test")
    assert summarizer.summarize(conv) is None
