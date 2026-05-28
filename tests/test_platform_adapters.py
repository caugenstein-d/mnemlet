"""Tests for platform-specific adapters."""

from mnemlet.intelligence.adapters import (
    OpenWebUIAdapter,
    ClaudeCodeAdapter,
    OpenCodeAdapter,
    OpenClawAdapter,
    CursorAdapter,
    ClaudeDesktopAdapter,
    GenericAdapter,
    get_adapter,
)


def test_openwebui_adapter_normalizes_messages():
    raw = {
        "chat_id": "chat-123",
        "messages": [
            {"role": "user", "content": "Hello", "timestamp": 1716883200},
            {"role": "assistant", "content": "Hi there!", "timestamp": 1716883201},
        ],
    }

    conv = OpenWebUIAdapter.normalize(raw)

    assert conv.platform == "openwebui"
    assert conv.session_id == "chat-123"
    assert len(conv.messages) == 2
    assert conv.messages[0].role == "user"
    assert conv.messages[1].role == "assistant"
    assert conv.namespace == "openwebui/default"


def test_cursor_adapter_normalizes_with_context():
    raw = {
        "conversation_id": "cursor-456",
        "messages": [
            {
                "role": "user",
                "content": "Fix this bug",
                "timestamp": "2026-05-28T10:00:00Z",
                "context": {"files": ["src/main.py"]},
            },
            {
                "role": "assistant",
                "content": "Fixed!",
                "timestamp": "2026-05-28T10:00:01Z",
                "code_changes": [{"file": "src/main.py", "diff": "..."}],
            },
        ],
    }

    conv = CursorAdapter.normalize(raw)

    assert conv.platform == "cursor"
    assert conv.session_id == "cursor-456"
    assert len(conv.messages) == 2
    assert "cursor_context" in conv.messages[0].metadata
    assert "cursor_code_changes" in conv.messages[1].metadata


def test_claude_desktop_adapter_normalizes_with_project():
    raw = {
        "conversation_id": "claude-789",
        "project": "mnemlet",
        "messages": [
            {"role": "user", "content": "Hello", "timestamp": 1716883200},
            {"role": "assistant", "content": "Hi!", "timestamp": 1716883201},
        ],
    }

    conv = ClaudeDesktopAdapter.normalize(raw)

    assert conv.platform == "claude_desktop"
    assert conv.namespace == "claude_desktop/mnemlet"
    assert conv.session_id == "claude-789"
    assert len(conv.messages) == 2


def test_claude_code_adapter_handles_iso_and_epoch_and_project():
    raw = {
        "session_id": "cc-1",
        "project": "mnemlet",
        "messages": [
            {"role": "user", "content": "ISO ts", "timestamp": "2026-05-28T10:00:00Z"},
            {"role": "assistant", "content": "epoch ts", "timestamp": 1716883201},
        ],
    }
    conv = ClaudeCodeAdapter.normalize(raw)
    assert conv.platform == "claude_code"
    assert conv.namespace == "claude_code/mnemlet"
    assert conv.session_id == "cc-1"
    assert conv.messages[0].timestamp is not None
    assert conv.messages[1].timestamp is not None


def test_opencode_and_openclaw_default_namespaces():
    raw = {"session_id": "s1", "messages": [{"role": "user", "content": "hi"}]}
    assert OpenCodeAdapter.normalize(raw).namespace == "opencode/default"
    assert OpenClawAdapter.normalize(raw).namespace == "openclaw/default"


def test_generic_adapter_is_permissive():
    raw = {
        "id": "gen-1",
        "namespace": "custom/ns",
        "messages": [
            {"role": "user", "content": "no timestamp here"},
            {"content": "missing role defaults to user"},
        ],
    }
    conv = GenericAdapter.normalize(raw)
    assert conv.platform == "generic"
    assert conv.session_id == "gen-1"
    assert conv.namespace == "custom/ns"
    assert conv.messages[0].timestamp is None
    assert conv.messages[1].role == "user"


def test_get_adapter_dispatch_and_fallback():
    assert get_adapter("openwebui") is OpenWebUIAdapter
    assert get_adapter("claude_code") is ClaudeCodeAdapter
    assert get_adapter("unknown-platform") is GenericAdapter
