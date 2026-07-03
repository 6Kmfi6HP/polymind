"""
Base agent implementing the observe-decide-act loop.

This is the core framework that all trading agents inherit from.
Subclasses must implement decide() with their trading logic.
"""

import asyncio
from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any

from pydantic import BaseModel


class Observation(BaseModel):
    """Market state observation."""
    timestamp: datetime
    markets: list[Any] = []
    positions: list[Any] = []
    balance: float = 0.0


class Decision(BaseModel):
    """Trading decision."""
    action: str  # "buy", "sell", "hold", "close"
    market_id: str | None = None
    outcome: str | None = None
    size: float = 0.0
    price: float | None = None
    reasoning: str = ""
    confidence: float = 0.5


class BaseAgent(ABC):
    """Abstract agent implementing observe → decide → act loop."""

    def __init__(
        self,
        client: Any = None,
        risk_manager: Any = None,
        name: str = "BaseAgent",
        loop_interval: int = 60,
        dry_run: bool = False,
    ):
        self.client = client
        self.risk_manager = risk_manager
        self.name = name
        self.loop_interval = loop_interval
        self.dry_run = dry_run
        self._running = False

    @abstractmethod
    async def decide(self, observation: Observation) -> Decision:
        """Make a trading decision based on observation."""
        ...

    async def observe(self) -> Observation:
        """Fetch current market state."""
        markets = []
        positions = []
        balance = 0.0

        if self.client and hasattr(self.client, "get_markets"):
            markets = await self.client.get_markets(active=True, limit=50)
        if self.client and hasattr(self.client, "get_positions"):
            positions = await self.client.get_positions()
        if self.client and hasattr(self.client, "get_balance"):
            balance = await self.client.get_balance()

        return Observation(
            timestamp=datetime.now(),
            markets=markets,
            positions=positions,
            balance=balance,
        )

    async def act(self, decision: Decision) -> bool:
        """Execute a trading decision."""
        if decision.action == "hold":
            return True
        if self.dry_run:
            return True
        # Actual execution delegated to subclasses or strategy
        return True

    async def run_loop(self) -> None:
        """Main agent loop."""
        self._running = True
        try:
            while self._running:
                obs = await self.observe()
                dec = await self.decide(obs)
                await self.act(dec)
                await asyncio.sleep(self.loop_interval)
        except asyncio.CancelledError:
            pass
        finally:
            self._running = False

    def stop(self) -> None:
        """Stop the agent loop."""
        self._running = False
