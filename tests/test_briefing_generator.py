"""Tests for the morning briefing generator (naive + LLM paths)."""

from pathlib import Path

from mnemlet.engine.sleep import SleepEngine
from mnemlet.storage.sqlite import MnemletDB


def _engine(tmp_path: Path, llm=None) -> tuple[SleepEngine, MnemletDB]:
    db = MnemletDB(tmp_path / "mnemlet.db")
    engine = SleepEngine(db=db, chroma=None, embedder=None, vault=None, llm=llm)
    return engine, db


def _briefings(db: MnemletDB) -> list:
    return db.conn.execute(
        "SELECT content_preview FROM memories WHERE namespace = '__system__/morning_briefing'"
    ).fetchall()


def test_naive_briefing_without_llm(tmp_path):
    engine, db = _engine(tmp_path)
    db.insert_memory(namespace="preferences", content_preview="prefers dark mode", importance=0.9)

    engine._task_prepare_briefing()

    rows = _briefings(db)
    assert len(rows) == 1
    assert "Morning Briefing" in rows[0]["content_preview"]
    db.close()


def test_llm_briefing_uses_model_output(tmp_path):
    class FakeLLM:
        def generate(self, prompt: str) -> str:
            return "## Current Projects\nMnémlet v0.4 intelligent extraction."

    engine, db = _engine(tmp_path, llm=FakeLLM())
    db.insert_memory(namespace="projects/mnemlet", content_preview="working on v0.4", importance=0.9)

    engine._task_prepare_briefing()

    rows = _briefings(db)
    assert len(rows) == 1
    assert "Mnémlet v0.4" in rows[0]["content_preview"]
    db.close()


def test_llm_failure_falls_back_to_naive(tmp_path):
    class BoomLLM:
        def generate(self, prompt: str) -> str:
            raise RuntimeError("ollama unreachable")

    engine, db = _engine(tmp_path, llm=BoomLLM())
    db.insert_memory(namespace="x", content_preview="something", importance=0.5)

    engine._task_prepare_briefing()

    rows = _briefings(db)
    assert len(rows) == 1
    assert "Morning Briefing" in rows[0]["content_preview"]  # naive header
    db.close()


def test_empty_db_produces_no_briefing(tmp_path):
    engine, db = _engine(tmp_path)
    engine._task_prepare_briefing()
    assert len(_briefings(db)) == 0
    db.close()
