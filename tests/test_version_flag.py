"""Test for --version flag."""

import subprocess
import sys


def test_version_flag():
    """mnemlet --version should print version and exit."""
    result = subprocess.run(
        [sys.executable, "-m", "mnemlet", "--version"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert "0.3.0" in result.stdout or "0.3.0" in result.stderr
