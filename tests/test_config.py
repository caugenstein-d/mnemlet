"""Tests for config loading."""

import tempfile
import os
from pathlib import Path
from engram.config import EngramConfig, load_config


def test_config_defaults():
    """Config has sensible defaults without any files."""
    cfg = EngramConfig()
    assert cfg.server_host == "127.0.0.1"
    assert cfg.server_port == 4050
    assert cfg.data_dir == Path.home() / ".engram"


def test_config_from_toml():
    """Config loads from TOML file."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
        f.write("""
[server]
host = "0.0.0.0"
port = 9999

[storage]
data_dir = "/tmp/engram-test"

[embedding]
model = "custom-model"
cache_dir = "/tmp/model-cache"
""")
        toml_path = f.name

    try:
        cfg = EngramConfig.from_toml(toml_path)
        assert cfg.server_host == "0.0.0.0"
        assert cfg.server_port == 9999
        assert cfg.data_dir == Path("/tmp/engram-test")
        assert cfg.embedding_model == "custom-model"
        assert cfg.embedding_cache_dir == Path("/tmp/model-cache")
    finally:
        os.unlink(toml_path)


def test_config_from_env():
    """Config overrides from environment variables."""
    os.environ["ENGRAM_HOST"] = "10.0.0.1"
    os.environ["ENGRAM_PORT"] = "8080"
    cfg = EngramConfig()
    assert cfg.server_host == "10.0.0.1"
    assert cfg.server_port == 8080
    del os.environ["ENGRAM_HOST"]
    del os.environ["ENGRAM_PORT"]


def test_config_data_dir_from_env():
    """ENGRAM_DATA_DIR env var overrides default."""
    os.environ["ENGRAM_DATA_DIR"] = "/tmp/engram-custom"
    cfg = EngramConfig()
    assert cfg.data_dir == Path("/tmp/engram-custom")
    assert cfg.sqlite_path == Path("/tmp/engram-custom/engram.db")
    del os.environ["ENGRAM_DATA_DIR"]
