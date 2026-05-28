"""Tests for conversation buffer."""

from datetime import datetime, timedelta
from mnemlet.intelligence.buffer import ConversationBuffer
from mnemlet.intelligence.conversation import Conversation, Message


def test_buffer_collects_messages():
    completed = []

    def on_complete(conv: Conversation):
        completed.append(conv)

    buffer = ConversationBuffer(
        on_session_complete=on_complete,
        inactivity_threshold=timedelta(minutes=10),
    )

    msg1 = Message(role="user", content="Hi", timestamp=datetime.now())
    msg2 = Message(role="assistant", content="Hello!", timestamp=datetime.now())

    buffer.add_message("session-1", msg1, platform="test", namespace="test")
    buffer.add_message("session-1", msg2, platform="test", namespace="test")

    # Not yet completed (still within inactivity threshold)
    assert len(completed) == 0

    # Flush manually
    buffer.flush_all()
    assert len(completed) == 1
    assert len(completed[0].messages) == 2


def test_buffer_flushes_when_full():
    completed = []

    def on_complete(conv: Conversation):
        completed.append(conv)

    buffer = ConversationBuffer(
        on_session_complete=on_complete,
        max_messages=3,
    )

    for i in range(3):
        msg = Message(role="user", content=f"Message {i}", timestamp=datetime.now())
        buffer.add_message("session-1", msg, platform="test", namespace="test")

    # Should auto-flush when max_messages reached
    assert len(completed) == 1
    assert len(completed[0].messages) == 3


def test_buffer_keeps_sessions_separate():
    completed = []
    buffer = ConversationBuffer(on_session_complete=completed.append)

    buffer.add_message("a", Message(role="user", content="from a"), platform="p", namespace="ns-a")
    buffer.add_message("b", Message(role="user", content="from b"), platform="p", namespace="ns-b")
    buffer.flush_all()

    assert {c.session_id for c in completed} == {"a", "b"}
    assert {c.namespace for c in completed} == {"ns-a", "ns-b"}


def test_buffer_stop_flushes_and_cancels_timer():
    completed = []
    buffer = ConversationBuffer(on_session_complete=completed.append)
    buffer.add_message("s", Message(role="user", content="hi"), platform="p", namespace="n")

    buffer.stop()

    assert len(completed) == 1
    assert buffer._timer is None
