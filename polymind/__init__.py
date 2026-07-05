"""
Polymind — AI-native market making for Polymarket.

Write market-making strategies in natural language. Let AI assemble,
tune, and execute them on Polymarket's CLOB.
"""

__version__ = "0.7.0"


def __getattr__(name):
    """Lazy imports for core classes."""
    lazy = {
        "BaseAgent": ("polymind.core.agent", "BaseAgent"),
        "PolymarketClient": ("polymind.polymarket.client", "PolymarketClient"),
        "RiskManager": ("polymind.risk.manager", "RiskManager"),
        "BacktestEngine": ("polymind.backtesting.engine", "BacktestEngine"),
        "Config": ("polymind.core.config", "Config"),
    }
    if name in lazy:
        mod, cls = lazy[name]
        from importlib import import_module

        return getattr(import_module(mod), cls)
    raise AttributeError(f"module 'polymind' has no attribute '{name}'")


__all__ = [
    "__version__",
    "BaseAgent",
    "PolymarketClient",
    "RiskManager",
    "BacktestEngine",
    "Config",
]
