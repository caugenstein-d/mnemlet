"""Single API-key authentication helpers."""

from __future__ import annotations

import hashlib
import secrets
from dataclasses import dataclass
from hmac import compare_digest


API_KEY_PREFIX = "mnemlet_"


@dataclass(frozen=True)
class AuthDecision:
    """Result of API-key validation."""

    allowed: bool
    authenticated: bool
    reason: str
    caller_identity: str | None = None


def new_api_key() -> str:
    """Generate a new Mnémlet API key for local configuration."""
    return API_KEY_PREFIX + secrets.token_urlsafe(32)


def key_configured(api_key: str | None) -> bool:
    """Return whether an API key is configured and non-blank."""
    return bool(api_key and api_key.strip())


def hash_key_identity(api_key: str) -> str:
    """Return a short stable identity hash without exposing the key."""
    return hashlib.sha256(api_key.encode("utf-8")).hexdigest()[:8]


def validate_api_key(configured_key: str | None, provided_key: str | None) -> AuthDecision:
    """Validate a provided key against configured auth state."""
    if not key_configured(configured_key):
        return AuthDecision(allowed=True, authenticated=False, reason="auth_not_configured")
    if not key_configured(provided_key):
        return AuthDecision(allowed=False, authenticated=False, reason="missing_api_key")
    if compare_digest(str(configured_key), str(provided_key)):
        return AuthDecision(
            allowed=True,
            authenticated=True,
            reason="authenticated",
            caller_identity=hash_key_identity(str(configured_key)),
        )
    return AuthDecision(allowed=False, authenticated=False, reason="invalid_api_key")


def extract_request_key(headers: dict[str, str]) -> str | None:
    """Extract a Mnémlet API key from supported HTTP headers."""
    direct = headers.get("x-mnemlet-key") or headers.get("X-Mnemlet-Key")
    if direct:
        return direct
    authorization = headers.get("authorization") or headers.get("Authorization")
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    return None
