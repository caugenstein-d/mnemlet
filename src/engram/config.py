"""Configuration loading from TOML files and environment variables."""

import os
from pathlib import Path
from typing import Optional


class EngramConfig:
    """Engram configuration with sensible defaults."""

    def __init__(
        self,
        server_host: str = "127.0.0.1",
        server_port: int = 4050,
        data_dir: Path = Path.home() / ".engram",
        sqlite_path: Optional[Path] = None,
        chroma_path: Optional[Path] = None,
        vault_path: Optional[Path] = None,
        embedding_model: str = "all-MiniLM-L6-v2",
        embedding_cache_dir: Optional[Path] = None,
    ):
        self.server_host = os.environ.get("ENGRAM_HOST", server_host)
        self.server_port = int(os.environ.get("ENGRAM_PORT", server_port))

        env_data_dir = os.environ.get("ENGRAM_DATA_DIR")
        if env_data_dir:
            data_dir = Path(env_data_dir).expanduser()

        self.data_dir = data_dir
        self.sqlite_path = sqlite_path or self.data_dir / "engram.db"
        self.chroma_path = chroma_path or self.data_dir / "chroma"
        self.vault_path = vault_path or self.data_dir / "vault"
        self.embedding_model = embedding_model
        self.embedding_cache_dir = embedding_cache_dir or self.data_dir / "models"

    @classmethod
    def from_toml(cls, path: str) -> "EngramConfig":
        """Load configuration from a TOML file."""
        import tomllib

        with open(path, "rb") as f:
            data = tomllib.load(f)

        server = data.get("server", {})
        storage = data.get("storage", {})
        embedding = data.get("embedding", {})

        return cls(
            server_host=server.get("host", "127.0.0.1"),
            server_port=server.get("port", 4050),
            data_dir=Path(storage.get("data_dir", "~/.engram")).expanduser(),
            sqlite_path=Path(storage["sqlite_path"]).expanduser() if storage.get("sqlite_path") else None,
            chroma_path=Path(storage["chroma_path"]).expanduser() if storage.get("chroma_path") else None,
            vault_path=Path(storage["vault_path"]).expanduser() if storage.get("vault_path") else None,
            embedding_model=embedding.get("model", "all-MiniLM-L6-v2"),
            embedding_cache_dir=Path(embedding["cache_dir"]).expanduser() if embedding.get("cache_dir") else None,
        )


def load_config(path: Optional[str] = None) -> EngramConfig:
    """Load configuration from a TOML path or return defaults."""
    if path:
        return EngramConfig.from_toml(path)
    return EngramConfig()
