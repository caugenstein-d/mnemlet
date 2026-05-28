"""Configuration loading from TOML files and environment variables."""

import os
from pathlib import Path
from typing import Optional


def _env_bool(name: str, default: bool) -> bool:
    """Read a boolean from the environment ('1', 'true', 'yes' → True)."""
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


class MnemletConfig:
    """Mnemlet configuration with sensible defaults."""

    def __init__(
        self,
        server_host: str = "127.0.0.1",
        server_port: int = 4050,
        data_dir: Path = Path.home() / ".mnemlet",
        sqlite_path: Optional[Path] = None,
        chroma_path: Optional[Path] = None,
        vault_path: Optional[Path] = None,
        embedding_model: str = "all-MiniLM-L6-v2",
        embedding_cache_dir: Optional[Path] = None,
        api_key: Optional[str] = None,
        cors_origins: Optional[list[str]] = None,
        llm_enabled: bool = False,
        llm_provider: str = "ollama",
        llm_model: str = "gemma4-e2b:q4_0",
        llm_base_url: str = "http://localhost:11434",
        llm_temperature: float = 0.3,
        llm_max_tokens: int = 4096,
        extraction_enabled: bool = False,
        extract_memories: bool = True,
        summarize_conversations: bool = True,
        inactivity_threshold_minutes: int = 10,
        max_buffer_messages: int = 100,
    ) -> None:
        self.server_host = os.environ.get("MNEMLET_HOST", server_host)
        self.server_port = int(os.environ.get("MNEMLET_PORT", server_port))
        self.api_key = os.environ.get("MNEMLET_API_KEY", api_key)
        self.cors_origins = cors_origins or ["http://localhost", "http://127.0.0.1"]

        env_data_dir = os.environ.get("MNEMLET_DATA_DIR")
        if env_data_dir:
            data_dir = Path(env_data_dir).expanduser()

        self.data_dir = data_dir
        self.sqlite_path = sqlite_path or self.data_dir / "mnemlet.db"
        self.chroma_path = chroma_path or self.data_dir / "chroma"
        self.vault_path = vault_path or self.data_dir / "vault"
        self.embedding_model = embedding_model
        self.embedding_cache_dir = embedding_cache_dir or self.data_dir / "models"

        # LLM backend (optional; off by default). Env can force-enable.
        self.llm_enabled = _env_bool("MNEMLET_LLM_ENABLED", llm_enabled)
        self.llm_provider = llm_provider
        self.llm_model = os.environ.get("MNEMLET_LLM_MODEL", llm_model)
        self.llm_base_url = os.environ.get("MNEMLET_LLM_BASE_URL", llm_base_url)
        self.llm_temperature = llm_temperature
        self.llm_max_tokens = llm_max_tokens

        # v0.4 intelligent extraction (optional; off by default).
        self.extraction_enabled = _env_bool("MNEMLET_EXTRACTION_ENABLED", extraction_enabled)
        self.extract_memories = extract_memories
        self.summarize_conversations = summarize_conversations
        self.inactivity_threshold_minutes = inactivity_threshold_minutes
        self.max_buffer_messages = max_buffer_messages

    @classmethod
    def from_toml(cls, path: str) -> "MnemletConfig":
        """Load configuration from a TOML file."""
        import tomllib

        with open(path, "rb") as f:
            data = tomllib.load(f)

        server = data.get("server", {})
        storage = data.get("storage", {})
        embedding = data.get("embedding", {})
        auth = data.get("auth", {})
        llm = data.get("llm", {})
        intelligence = data.get("intelligence", {})

        return cls(
            server_host=server.get("host", "127.0.0.1"),
            server_port=server.get("port", 4050),
            data_dir=Path(storage.get("data_dir", "~/.mnemlet")).expanduser(),
            sqlite_path=Path(storage["sqlite_path"]).expanduser() if storage.get("sqlite_path") else None,
            chroma_path=Path(storage["chroma_path"]).expanduser() if storage.get("chroma_path") else None,
            vault_path=Path(storage["vault_path"]).expanduser() if storage.get("vault_path") else None,
            embedding_model=embedding.get("model", "all-MiniLM-L6-v2"),
            embedding_cache_dir=Path(embedding["cache_dir"]).expanduser() if embedding.get("cache_dir") else None,
            api_key=auth.get("api_key"),
            cors_origins=server.get("cors_origins"),
            llm_enabled=llm.get("enabled", False),
            llm_provider=llm.get("provider", "ollama"),
            llm_model=llm.get("model", "gemma4-e2b:q4_0"),
            llm_base_url=llm.get("base_url", "http://localhost:11434"),
            llm_temperature=llm.get("temperature", 0.3),
            llm_max_tokens=llm.get("max_tokens", 4096),
            extraction_enabled=intelligence.get("extraction_enabled", False),
            extract_memories=intelligence.get("extract_memories", True),
            summarize_conversations=intelligence.get("summarize_conversations", True),
            inactivity_threshold_minutes=intelligence.get("inactivity_threshold_minutes", 10),
            max_buffer_messages=intelligence.get("max_messages", 100),
        )


def load_config(path: Optional[str] = None) -> MnemletConfig:
    """Load configuration from a TOML path or return defaults."""
    if path:
        return MnemletConfig.from_toml(path)
    return MnemletConfig()
