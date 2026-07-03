"""
Core engine: agent loop, config, strategy base class, and intent/executor layer.

The Agent loop implements observe → decide → act, the core abstraction
that all Polymind strategies inherit from.

Per ADR 0002, strategies produce ``StrategyIntent`` objects and executors
own CLOB transport.  See :mod:`polymind.core.intents` for the contract.
"""

from polymind.core.agent import BaseAgent
from polymind.core.config import Config
from polymind.core.fills import FillEvent, FillSource
from polymind.core.intents import IntentExecutor, StrategyIntent
from polymind.core.portfolio import PortfolioTarget, PositionDirection
from polymind.core.strategy import BaseMMStrategy

__all__ = [
    "BaseAgent",
    "BaseMMStrategy",
    "Config",
    "FillEvent",
    "FillSource",
    "IntentExecutor",
    "PortfolioTarget",
    "PositionDirection",
    "StrategyIntent",
]
