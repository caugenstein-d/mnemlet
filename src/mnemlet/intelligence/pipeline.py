"""Memory extraction pipeline: buffer → extract → ingest."""

from datetime import timedelta
from typing import Any
from .buffer import ConversationBuffer
from .extractor import MemoryExtractor
from .summarizer import ConversationSummarizer
from .conversation import Conversation, Message


class ExtractionPipeline:
    """
    Orchestrates memory extraction from conversations.

    Flow:
    1. Conversation buffer collects messages
    2. On session complete:
       a. Extract individual memories (preferences, facts, decisions)
       b. Summarize entire conversation
       c. Ingest all memories into Mnémlet
    """

    def __init__(
        self,
        ingest_engine: Any,
        llm_client: Any,
        extract_memories: bool = True,
        summarize_conversations: bool = True,
        inactivity_threshold_minutes: int = 10,
        max_messages: int = 100,
    ):
        self.ingest = ingest_engine
        self.extractor = MemoryExtractor(llm_client) if extract_memories else None
        self.summarizer = ConversationSummarizer(llm_client) if summarize_conversations else None

        self.buffer = ConversationBuffer(
            on_session_complete=self._process_session,
            inactivity_threshold=timedelta(minutes=inactivity_threshold_minutes),
            max_messages=max_messages,
        )

    def add_message(self, session_key: str, message: Any, platform: str, namespace: str):
        """Add a message to the buffer.

        ``message`` may be a unified ``Message`` or a plain dict with
        ``role``/``content``/``timestamp`` keys.
        """
        if isinstance(message, Message):
            msg = message
            msg.metadata.setdefault("platform", platform)
            msg.metadata.setdefault("namespace", namespace)
        else:
            msg = Message(
                role=message.get("role", "user"),
                content=message.get("content", ""),
                timestamp=message.get("timestamp"),
                metadata={"platform": platform, "namespace": namespace},
            )
        self.buffer.add_message(session_key, msg, platform, namespace)

    def _process_session(self, conversation: Conversation):
        """Process a completed session: extract, summarize, and ingest."""
        memories_to_ingest: list[dict] = []

        # Extract individual memories
        if self.extractor:
            try:
                memories_to_ingest.extend(self.extractor.extract(conversation))
            except Exception as e:  # noqa: BLE001 - background task must not crash
                print(f"[extraction] extractor failed: {e}")

        # Summarize conversation
        if self.summarizer:
            try:
                summary = self.summarizer.summarize(conversation)
                if summary:
                    memories_to_ingest.append(summary)
            except Exception as e:  # noqa: BLE001
                print(f"[extraction] summarizer failed: {e}")

        # Ingest all memories (one bad memory must not abort the rest)
        for mem in memories_to_ingest:
            if not mem or not mem.get("content"):
                continue
            try:
                self.ingest.ingest(
                    content=mem["content"],
                    namespace=mem.get("namespace", conversation.namespace),
                    importance=mem.get("importance", 0.5),
                    metadata={
                        "source": "extraction_pipeline",
                        "platform": conversation.platform,
                        "session_id": conversation.session_id,
                        "extracted_type": mem.get("type"),
                    },
                )
            except Exception as e:  # noqa: BLE001
                print(f"[extraction] ingest failed for one memory: {e}")

    def flush(self):
        """Flush all buffered sessions."""
        self.buffer.flush_all()

    def stop(self):
        """Stop the pipeline."""
        self.buffer.stop()
