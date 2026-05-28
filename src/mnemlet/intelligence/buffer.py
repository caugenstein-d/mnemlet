"""Conversation buffer for session detection and batching."""

import threading
from datetime import datetime, timedelta
from typing import Callable
from .conversation import Conversation, Message


class ConversationBuffer:
    """
    Buffers incoming messages and detects session boundaries.

    Session ends when:
    - No new messages for `inactivity_threshold` (default: 10 minutes)
    - Explicit flush() call
    - Buffer size exceeds `max_messages` (default: 100)
    """

    def __init__(
        self,
        on_session_complete: Callable[[Conversation], None],
        inactivity_threshold: timedelta = timedelta(minutes=10),
        max_messages: int = 100,
    ):
        self.on_session_complete = on_session_complete
        self.inactivity_threshold = inactivity_threshold
        self.max_messages = max_messages

        self._buffers: dict[str, list[Message]] = {}  # session_key -> messages
        self._last_activity: dict[str, datetime] = {}
        self._lock = threading.RLock()
        self._timer: threading.Timer | None = None

    def add_message(self, session_key: str, message: Message, platform: str, namespace: str):
        """Add a message to the buffer."""
        # Stamp platform/namespace onto the message metadata so inactivity-based
        # flushes (which only see buffered messages) can reconstruct context.
        message.metadata.setdefault("platform", platform)
        message.metadata.setdefault("namespace", namespace)
        with self._lock:
            if session_key not in self._buffers:
                self._buffers[session_key] = []
            self._buffers[session_key].append(message)
            self._last_activity[session_key] = datetime.now()

            # Check if buffer is full
            if len(self._buffers[session_key]) >= self.max_messages:
                self._flush_session(session_key, platform, namespace)

            # Reset inactivity timer while still holding the lock.
            self._reset_timer()

    def _reset_timer(self):
        """Reset the inactivity timer (caller holds the lock)."""
        if self._timer:
            self._timer.cancel()
            self._timer = None
        if not self._buffers:
            return
        self._timer = threading.Timer(
            self.inactivity_threshold.total_seconds(),
            self._check_inactivity,
        )
        # Daemon so a pending timer never blocks interpreter/process exit.
        self._timer.daemon = True
        self._timer.start()

    def _check_inactivity(self):
        """Check for inactive sessions and flush them."""
        now = datetime.now()
        with self._lock:
            for session_key in list(self._buffers.keys()):
                last = self._last_activity.get(session_key, now)
                if now - last >= self.inactivity_threshold:
                    first_msg = self._buffers[session_key][0]
                    platform = first_msg.metadata.get("platform", "generic")
                    namespace = first_msg.metadata.get("namespace", "default")
                    self._flush_session(session_key, platform, namespace)
            self._reset_timer()

    def _flush_session(self, session_key: str, platform: str, namespace: str):
        """Flush a session buffer and trigger processing (caller holds the lock)."""
        if session_key not in self._buffers or not self._buffers[session_key]:
            return

        messages = self._buffers.pop(session_key)
        self._last_activity.pop(session_key, None)

        conversation = Conversation(
            messages=messages,
            platform=platform,
            session_id=session_key,
            namespace=namespace,
            started_at=messages[0].timestamp,
            ended_at=messages[-1].timestamp,
        )

        # Trigger callback
        self.on_session_complete(conversation)

    def flush_all(self):
        """Flush all buffered sessions."""
        with self._lock:
            for session_key in list(self._buffers.keys()):
                first_msg = self._buffers[session_key][0]
                platform = first_msg.metadata.get("platform", "generic")
                namespace = first_msg.metadata.get("namespace", "default")
                self._flush_session(session_key, platform, namespace)
            self._reset_timer()

    def stop(self):
        """Stop the buffer and flush remaining sessions."""
        with self._lock:
            if self._timer:
                self._timer.cancel()
                self._timer = None
        self.flush_all()

    def shutdown(self):
        """Cancel the timer and drop buffered messages WITHOUT flushing.

        Used on server shutdown so a slow LLM flush can't block the event
        loop from stopping. Buffered chat fragments are transient and safe
        to discard.
        """
        with self._lock:
            if self._timer:
                self._timer.cancel()
                self._timer = None
            self._buffers.clear()
            self._last_activity.clear()
