"""Contract tests for the OpenWebUI Mnémlet filter.

These tests never contact OpenWebUI or Mnémlet. They import the filter file and monkeypatch
its REST helper.
"""

from __future__ import annotations

import importlib.util
import os
from pathlib import Path
from types import ModuleType

import pytest


DEFAULT_FILTER_PATH = Path(__file__).parent / "fixtures" / "openwebui" / "mnemlet_valve.py"


def _filter_path_from_env() -> Path:
    return Path(os.environ.get("MNEMLET_FILTER_PATH", str(DEFAULT_FILTER_PATH)))


@pytest.fixture
def filter_path() -> Path:
    return _filter_path_from_env()


@pytest.fixture
def filter_module(filter_path: Path) -> ModuleType:
    if not filter_path.exists():
        pytest.fail(f"OpenWebUI filter not found at {filter_path}")
    spec = importlib.util.spec_from_file_location("mnemlet_valve_contract", filter_path)
    if spec is None or spec.loader is None:
        pytest.fail(f"Cannot load filter module from {filter_path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_inlet_returns_body_unchanged_on_empty_results(filter_module: ModuleType) -> None:
    calls = []

    def fake_post_json(path: str, payload: dict, timeout: int) -> dict:
        calls.append((path, payload, timeout))
        return {"results": []}

    filter_module._post_json = fake_post_json
    body = {"messages": [{"role": "user", "content": "unknown topic"}]}

    returned = filter_module.Filter().inlet(body)

    assert returned == {"messages": [{"role": "user", "content": "unknown topic"}]}
    assert calls


def test_inlet_returns_body_unchanged_on_abstention_response(filter_module: ModuleType) -> None:
    def fake_post_json(path: str, payload: dict, timeout: int) -> dict:
        return {"context_pack": {"primary": [], "supporting": [], "superseded": []}, "abstention": {"reason": "no_relevant_memories"}}

    filter_module._post_json = fake_post_json
    body = {"messages": [{"role": "user", "content": "unknown topic"}]}

    returned = filter_module.Filter().inlet(body)

    assert returned == {"messages": [{"role": "user", "content": "unknown topic"}]}


def test_inlet_returns_body_unchanged_on_timeout(filter_module: ModuleType) -> None:
    def fake_post_json(path: str, payload: dict, timeout: int) -> dict:
        raise TimeoutError("slow memory")

    filter_module._post_json = fake_post_json
    body = {"messages": [{"role": "user", "content": "What is the bridge codename?"}]}

    returned = filter_module.Filter().inlet(body)

    assert returned == {"messages": [{"role": "user", "content": "What is the bridge codename?"}]}


def test_filter_fixture_path_exists_by_default(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("MNEMLET_FILTER_PATH", raising=False)

    path = _filter_path_from_env()

    assert path == DEFAULT_FILTER_PATH
    assert path.exists()


def test_filter_module_loads_repo_local_fixture(filter_module: ModuleType) -> None:
    assert hasattr(filter_module, "Filter")
    assert filter_module.Filter().priority == 0
