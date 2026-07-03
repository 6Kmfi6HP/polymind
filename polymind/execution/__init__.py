"""
Execution layer: intent -> order lifecycle, fill simulation, paper trading.

Phase 3 components bridge strategy intents and exchange-specific transport.
"""

from __future__ import annotations

from polymind.execution.executor import OrderRecord, OrderStatus, PaperExecutor, PositionRecord
from polymind.execution.fill_model import FillMode, FillModel, FillModelConfig, FillResult, MarketSnapshot
from polymind.execution.order_identity import OrderIdentity
from polymind.execution.persistence import LedgerStore
from polymind.execution.safety import KillSwitch, LogRedaction, PreflightChecker, PreflightResult

__all__ = [
    "FillMode",
    "FillModel",
    "FillModelConfig",
    "FillResult",
    "KillSwitch",
    "LedgerStore",
    "LogRedaction",
    "MarketSnapshot",
    "OrderIdentity",
    "OrderRecord",
    "OrderStatus",
    "PaperExecutor",
    "PositionRecord",
    "PreflightChecker",
    "PreflightResult",
]
