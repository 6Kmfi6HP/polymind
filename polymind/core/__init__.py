"""
Core engine: agent loop, config, strategy base class, and intent/executor layer.

The Agent loop implements observe → decide → act, the core abstraction
that all Polymind strategies inherit from.

Per ADR 0002, strategies produce ``StrategyIntent`` objects and executors
own CLOB transport.  See :mod:`polymind.core.intents` for the contract.
"""

from polymind.core import discover as plugin_discover
from polymind.core.agent import BaseAgent
from polymind.core.config import Config
from polymind.core.fills import FillEvent, FillSource
from polymind.core.intents import IntentExecutor, StrategyIntent
from polymind.core.ledger import EntryType, LedgerEntry
from polymind.core.plugin import PluginRegistry
from polymind.core.portfolio import PortfolioTarget, PositionDirection
from polymind.core.risk import RiskContext, RiskDecision, RiskGate
from polymind.core.strategy import BaseMMStrategy
from polymind.core.workflows import CommandType, WorkflowCommand

__all__ = [
    "BaseAgent",
    "BaseMMStrategy",
    "CommandType",
    "Config",
    "EntryType",
    "FillEvent",
    "FillSource",
    "IntentExecutor",
    "LedgerEntry",
    "PluginRegistry",
    "PortfolioTarget",
    "PositionDirection",
    "RiskContext",
    "RiskDecision",
    "RiskGate",
    "StrategyIntent",
    "WorkflowCommand",
    "plugin_discover",
]
