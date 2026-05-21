"""Tests for environment-dependent live benchmark checks."""

from __future__ import annotations

import subprocess
from io import BytesIO

import pytest

from mnemlet.benchmark.live import run_live_checks


def test_run_live_checks_returns_empty_by_default() -> None:
    assert run_live_checks() == []


def test_run_live_checks_runs_both_opencode_checks(monkeypatch: pytest.MonkeyPatch) -> None:
    calls: list[list[str]] = []
    timeouts: list[int] = []

    def fake_run(command: list[str], **kwargs: object) -> subprocess.CompletedProcess[str]:
        calls.append(command)
        timeouts.append(int(kwargs["timeout"]))
        if command == ["opencode", "mcp", "list"]:
            return subprocess.CompletedProcess(command, 0, stdout="mnemlet connected\n", stderr="")
        if command[:2] == ["opencode", "run"]:
            return subprocess.CompletedProcess(command, 0, stdout="Nebelkrähe\n", stderr="")
        raise AssertionError(f"unexpected command: {command}")

    monkeypatch.setattr(subprocess, "run", fake_run)

    results = run_live_checks(include_opencode=True)

    assert calls == [
        ["opencode", "mcp", "list"],
        ["opencode", "run", "What is the Mnémlet OpenCode bridge called? Answer with only the codename."],
    ]
    assert timeouts == [30, 120]
    assert results == [
        {"name": "opencode_mcp_list", "surface": "opencode-live", "success": True},
        {"name": "opencode_sentinel", "surface": "opencode-live", "success": True},
    ]


def test_run_live_checks_reports_opencode_subprocess_failures(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run(_command: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        raise TimeoutError("command timed out")

    monkeypatch.setattr(subprocess, "run", fake_run)

    results = run_live_checks(include_opencode=True)

    assert len(results) == 2
    assert results[0]["success"] is False
    assert results[0]["error"] == "command timed out"
    assert results[1]["success"] is False
    assert results[1]["error"] == "command timed out"


def test_run_live_checks_reports_opencode_timeout_expired(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run(command: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        raise subprocess.TimeoutExpired(command, timeout=5)

    monkeypatch.setattr(subprocess, "run", fake_run)

    results = run_live_checks(include_opencode=True)

    assert len(results) == 2
    assert results[0]["success"] is False
    assert "timed out" in results[0]["error"]


def test_run_live_checks_reports_opencode_return_code_and_output(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_run(command: list[str], **_kwargs: object) -> subprocess.CompletedProcess[str]:
        return subprocess.CompletedProcess(command, 7, stdout="partial stdout", stderr="partial stderr")

    monkeypatch.setattr(subprocess, "run", fake_run)

    results = run_live_checks(include_opencode=True)

    assert results[0]["success"] is False
    assert results[0]["returncode"] == 7
    assert results[0]["stdout"] == "partial stdout"
    assert results[0]["stderr"] == "partial stderr"


def test_run_live_checks_fetches_openwebui_version(monkeypatch: pytest.MonkeyPatch) -> None:
    class Response(BytesIO):
        status = 200

        def __enter__(self) -> "Response":
            return self

        def __exit__(self, *_args: object) -> None:
            return None

    def fake_urlopen(url: str, timeout: int) -> Response:
        assert url == "http://127.0.0.1:8080/_app/version.json"
        assert timeout == 5
        return Response(b'{"version":"test"}')

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    assert run_live_checks(include_openwebui=True) == [
        {"name": "openwebui_version", "surface": "openwebui-live", "success": True, "body": '{"version":"test"}'}
    ]


def test_run_live_checks_caps_openwebui_version_body(monkeypatch: pytest.MonkeyPatch) -> None:
    class Response(BytesIO):
        status = 200

        def __enter__(self) -> "Response":
            return self

        def __exit__(self, *_args: object) -> None:
            return None

    monkeypatch.setattr("urllib.request.urlopen", lambda _url, timeout: Response(b"x" * 3000))

    result = run_live_checks(include_openwebui=True)[0]

    assert len(result["body"]) == 2000


def test_run_live_checks_reports_openwebui_exception(monkeypatch: pytest.MonkeyPatch) -> None:
    def fake_urlopen(_url: str, timeout: int) -> object:
        raise OSError("connection refused")

    monkeypatch.setattr("urllib.request.urlopen", fake_urlopen)

    results = run_live_checks(include_openwebui=True)

    assert results == [
        {
            "name": "openwebui_version",
            "surface": "openwebui-live",
            "success": False,
            "error": "connection refused",
        }
    ]
