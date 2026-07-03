"""
Execution layer: intent → order lifecycle, fill simulation, paper trading.

Phase 3 components bridge strategy intents and exchange-specific transport.
"""

from __future__ import annotations

from polymind.execution.order_identity import OrderIdentity

__all__ = [
    "OrderIdentity",
]
