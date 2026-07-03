"""
Secure credential management for Polymind.

Reads secrets from environment variables prefixed with a configurable
namespace.  Also provides a utility to mask sensitive strings for display.
"""

from __future__ import annotations

import os


class SecretNotFound(Exception):
    """Raised when a requested secret is not set in the environment."""


class SecretsManager:
    """Reads secrets from environment variables.

    Every lookup builds the variable name as ``{PREFIX}_{NAME}``
    where *PREFIX* is the configured ``env_prefix`` (default ``POLYMIND_``)
    and *NAME* is the upper-cased argument passed to ``get`` / ``get_or_raise``.

    Args:
        env_prefix: Prefix for environment variable names, including the
            trailing underscore (e.g. ``"POLYMIND_"``).
    """

    def __init__(self, env_prefix: str = "POLYMIND_") -> None:
        self._prefix = env_prefix.strip().upper().rstrip("_")

    def _env_key(self, name: str) -> str:
        return f"{self._prefix}_{name.upper()}"

    def get(self, name: str) -> str | None:
        """Return the secret *name* or ``None`` if not set."""
        return os.getenv(self._env_key(name))

    def get_or_raise(self, name: str) -> str:
        """Return the secret *name* or raise :class:`SecretNotFound`."""
        value = self.get(name)
        if value is None:
            raise SecretNotFound(f"Secret '{self._env_key(name)}' is not set in the environment")
        return value


def mask(value: str, keep_first: int = 6, keep_last: int = 4) -> str:
    """Mask the middle portion of *value*, showing only the first and last characters.

    Args:
        value: The sensitive string to mask.
        keep_first: Number of leading characters to show.
        keep_last: Number of trailing characters to show.

    Returns:
        Masked string like ``"abc123...xyzw"``.  If the string is short
        enough that masking would hide nothing, it is returned unchanged.
    """
    if len(value) <= keep_first + keep_last:
        return value
    return value[:keep_first] + "..." + value[-keep_last:]
