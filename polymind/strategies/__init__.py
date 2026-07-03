"""
Strategy registry — discovers and manages all available market-making strategies.
"""

from typing import Any

from polymind.core.strategy import BaseMMStrategy

_registry: dict[str, type] = {}


def register(name: str):
    """Decorator to register a strategy."""

    def decorator(cls):
        _registry[name] = cls
        return cls

    return decorator


def get_strategy(name: str, config: Any | None = None) -> BaseMMStrategy:
    """Instantiate a registered strategy by name."""
    if name not in _registry:
        available = ", ".join(sorted(_registry.keys()))
        raise ValueError(f"Unknown strategy '{name}'. Available: {available}")
    return _registry[name](config)


def list_strategies() -> dict[str, str]:
    """List all registered strategies with descriptions."""
    return {name: cls.__doc__ or "" for name, cls in _registry.items()}


__all__ = ["register", "get_strategy", "list_strategies"]
