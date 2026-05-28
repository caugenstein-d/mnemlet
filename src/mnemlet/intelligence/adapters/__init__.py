"""Platform-specific adapters for conversation normalization."""

from .openwebui import OpenWebUIAdapter
from .claude_code import ClaudeCodeAdapter
from .opencode import OpenCodeAdapter
from .openclaw import OpenClawAdapter
from .cursor import CursorAdapter
from .claude_desktop import ClaudeDesktopAdapter
from .generic import GenericAdapter

__all__ = [
    "OpenWebUIAdapter",
    "ClaudeCodeAdapter",
    "OpenCodeAdapter",
    "OpenClawAdapter",
    "CursorAdapter",
    "ClaudeDesktopAdapter",
    "GenericAdapter",
    "ADAPTERS",
    "get_adapter",
]


# Registry mapping platform name → adapter class, for dispatch by name.
ADAPTERS = {
    "openwebui": OpenWebUIAdapter,
    "claude_code": ClaudeCodeAdapter,
    "opencode": OpenCodeAdapter,
    "openclaw": OpenClawAdapter,
    "cursor": CursorAdapter,
    "claude_desktop": ClaudeDesktopAdapter,
    "generic": GenericAdapter,
}


def get_adapter(platform: str):
    """Return the adapter class for a platform, falling back to GenericAdapter."""
    return ADAPTERS.get(platform, GenericAdapter)
