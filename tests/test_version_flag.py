"""Test for --version flag."""

import subprocess
import sys

from mnemlet import __version__


def test_version_flag():
    """mnemlet --version should print version and exit."""
    result = subprocess.run(
        [sys.executable, "-m", "mnemlet", "--version"],
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0
    assert __version__ in result.stdout or __version__ in result.stderr
