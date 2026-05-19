"""Tests for config loading."""

import tempfile
import os
from pathlib import Path
from mnemlet.config import MnemletConfig, load_config


def test_config_defaults():
    """Config has sensible defaults without any files."""
    cfg = MnemletConfig()
    assert cfg.server_host == "127.0.0.1"
    assert cfg.server_port == 4050
    assert cfg.data_dir == Path.home() / ".mnemlet"


def test_config_from_toml():
    """Config loads from TOML file."""
    with tempfile.NamedTemporaryFile(mode="w", suffix=".toml", delete=False) as f:
        f.write("""
[server]
host = "0.0.0.0"
port = 9999

[storage]
data_dir = "/tmp/mnemlet-test"

[embedding]
model = "custom-model"
cache_dir = "/tmp/model-cache"
""")
        toml_path = f.name

    try:
        cfg = MnemletConfig.from_toml(toml_path)
        assert cfg.server_host == "0.0.0.0"
        assert cfg.server_port == 9999
        assert cfg.data_dir == Path("/tmp/mnemlet-test")
        assert cfg.embedding_model == "custom-model"
        assert cfg.embedding_cache_dir == Path("/tmp/model-cache")
    finally:
        os.unlink(toml_path)


def test_config_from_env():
    """Config overrides from environment variables."""
    os.environ["MNEMLET_HOST"] = "10.0.0.1"
    os.environ["MNEMLET_PORT"] = "8080"
    cfg = MnemletConfig()
    assert cfg.server_host == "10.0.0.1"
    assert cfg.server_port == 8080
    del os.environ["MNEMLET_HOST"]
    del os.environ["MNEMLET_PORT"]


def test_config_data_dir_from_env():
    """MNEMLET_DATA_DIR env var overrides default."""
    os.environ["MNEMLET_DATA_DIR"] = "/tmp/mnemlet-custom"
    cfg = MnemletConfig()
    assert cfg.data_dir == Path("/tmp/mnemlet-custom")
    assert cfg.sqlite_path == Path("/tmp/mnemlet-custom/mnemlet.db")
    del os.environ["MNEMLET_DATA_DIR"]
