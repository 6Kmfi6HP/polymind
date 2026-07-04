"""
Strategy registry — discovers and manages all available market-making strategies.
"""

from typing import Any

from polymind.core.plugin import PluginRegistry
from polymind.core.strategy import BaseMMStrategy

_registry: dict[str, type] = {}


def register(name: str):
    """Decorator to register a strategy."""

    def decorator(cls):
        _registry[name] = cls
        if PluginRegistry().get_strategy(name) is None:
            PluginRegistry().register_strategy(name, cls)
        return cls

    return decorator


def get_strategy(name: str, config: Any | None = None) -> BaseMMStrategy:
    """Instantiate a registered strategy by name."""
    if name in _registry:
        return _registry[name](config)
    cls = PluginRegistry().get_strategy(name)
    if cls is None:
        available = ", ".join(
            sorted(set(_registry.keys()) | set(PluginRegistry().list_strategies().keys()))
        )
        raise ValueError(f"Unknown strategy '{name}'. Available: {available}")
    return cls(config)


def list_strategies() -> dict[str, str]:
    """List all registered strategies with descriptions."""
    result = {name: cls.__doc__ or "" for name, cls in _registry.items()}
    for name, cls in PluginRegistry().list_strategies().items():
        if name not in result:
            result[name] = cls.__doc__ or ""
    return result


def register_builtin_strategies() -> None:
    """Register all built-in strategies into PluginRegistry."""
    from polymind.strategies.market_making.amm import AMMStrategy
    from polymind.strategies.market_making.bands import BandsStrategy
    from polymind.strategies.market_making.classic_mm.strategy import ClassicMMStrategy

    for name, cls in [
        ("amm", AMMStrategy),
        ("bands", BandsStrategy),
        ("classic_mm", ClassicMMStrategy),
    ]:
        if name not in _registry:
            _registry[name] = cls
        if PluginRegistry().get_strategy(name) is None:
            PluginRegistry().register_strategy(name, cls)


register_builtin_strategies()

__all__ = [
    "get_strategy",
    "list_strategies",
    "register",
    "register_builtin_strategies",
]
