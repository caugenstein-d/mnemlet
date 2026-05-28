"""Tests for unified conversation format."""

from datetime import datetime
from mnemlet.intelligence.conversation import Conversation, Message, parse_timestamp


def test_message_creation():
    msg = Message(role="user", content="Hello", timestamp=datetime.now())
    assert msg.role == "user"
    assert msg.content == "Hello"


def test_conversation_serialization():
    conv = Conversation(
        messages=[
            Message(role="user", content="Hi", timestamp=datetime(2026, 5, 28, 10, 0)),
            Message(role="assistant", content="Hello!", timestamp=datetime(2026, 5, 28, 10, 1)),
        ],
        platform="openwebui",
        session_id="test-123",
        namespace="openwebui/test",
    )

    data = conv.to_dict()
    assert data["platform"] == "openwebui"
    assert len(data["messages"]) == 2

    restored = Conversation.from_dict(data)
    assert restored.platform == "openwebui"
    assert len(restored.messages) == 2
    assert restored.messages[0].content == "Hi"


def test_parse_timestamp_handles_multiple_formats():
    assert parse_timestamp(None) is None
    assert isinstance(parse_timestamp(1716883200), datetime)
    assert isinstance(parse_timestamp("2026-05-28T10:00:00Z"), datetime)
    existing = datetime(2026, 5, 28, 10, 0)
    assert parse_timestamp(existing) is existing
    assert parse_timestamp("not-a-date") is None
