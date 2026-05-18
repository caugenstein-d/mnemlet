"""Tests for config loading."""

import tempfile
import os
from pathlib import Path
from memoria.config import MemoriaConfig, load_config


def test_config_defaults():
    """Config has sensible defaults without any files."""
    cfg = MemoriaConfig()
    assert cfg.server_host == "127.0.0.1"
    assert cfg.server_port == 4050
    assert cfg.data_dir == Path.home() / ".memoria"


def test_config_from_toml():
    """Config loads from TOML file."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
        f.write("""
[server]
host = "0.0.0.0"
port = 9999

[storage]
data_dir = "/tmp/memoria-test"
""")
        toml_path = f.name

    try:
        cfg = MemoriaConfig.from_toml(toml_path)
        assert cfg.server_host == "0.0.0.0"
        assert cfg.server_port == 9999
        assert cfg.data_dir == Path("/tmp/memoria-test")
    finally:
        os.unlink(toml_path)


def test_config_from_env():
    """Config overrides from environment variables."""
    os.environ["MEMORIA_HOST"] = "10.0.0.1"
    os.environ["MEMORIA_PORT"] = "8080"
    cfg = MemoriaConfig()
    assert cfg.server_host == "10.0.0.1"
    assert cfg.server_port == 8080
    del os.environ["MEMORIA_HOST"]
    del os.environ["MEMORIA_PORT"]
