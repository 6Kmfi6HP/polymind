"""
Base agent implementing the observe-decide-act loop.

This is the core framework that all trading agents inherit from.
Subclasses must implement decide() with their trading logic.
"""

import asyncio
from abc import ABC, abstractmethod
from collections import deque
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


class AgentMemory(BaseModel):
    """Bounded memory for recent observations and decisions.

    Mirrors the pattern from probablyprofit-ai-framework:
    bounded deque collection for observations/decisions with
    optional database persistence and thread-safe access.

    Reference: probablyprofit/agent/base.py:AgentMemory
    """

    observations: deque[Observation] = deque(maxlen=100)
    decisions: deque[Decision] = deque(maxlen=100)
    enable_persistence: bool = False

    # Internal: lock is not a model field
    _lock: asyncio.Lock | None = None

    def model_post_init(self, __context: Any) -> None:
        """Initialise the async lock after pydantic init."""
        self._lock = asyncio.Lock()

    @property
    def lock(self) -> asyncio.Lock:
        if self._lock is None:
            self._lock = asyncio.Lock()
        return self._lock

    async def add_observation(self, observation: Observation) -> None:
        """Record an observation (thread-safe)."""
        async with self.lock:
            self.observations.append(observation)

    async def add_decision(self, decision: Decision) -> None:
        """Record a decision (thread-safe)."""
        async with self.lock:
            self.decisions.append(decision)

    def get_recent_history(self, n: int = 10) -> str:
        """Return formatted summary of the last n observation/decision pairs."""
        history: list[str] = []
        obs_list = list(self.observations)[-n:]
        dec_list = list(self.decisions)[-n:]
        for obs, dec in zip(obs_list, dec_list, strict=False):
            history.append(
                f"Time: {obs.timestamp.isoformat() if isinstance(obs.timestamp, datetime) else obs.timestamp}\n"
                f"  Markets: {len(obs.markets)}  Balance: {obs.balance}\n"
                f"  Decision: {dec.action} — {dec.reasoning[:80] if dec.reasoning else 'no reasoning'}"
            )
        return "\n".join(history)


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
        self.memory = AgentMemory()
        self._open_positions: set[str] = set()  # Track "market_id:outcome" positions (REF-001b)

    def _has_position(self, market_id: str, outcome: str) -> bool:
        """Check if we already have a position in this market/outcome.

        REF-001b: Ported from probablyprofit/agent/base.py:337-340.
        """
        return f"{market_id}:{outcome}" in self._open_positions

    def _record_position(self, market_id: str, outcome: str) -> None:
        """Record a position for dedup tracking.

        REF-001b: Ported from probablyprofit/agent/base.py:342-345.
        """
        self._open_positions.add(f"{market_id}:{outcome}")

    def _discard_position(self, market_id: str, outcome: str) -> None:
        """Remove a position from tracking (on sell/close).

        REF-001b: Complementary to _record_position; not in reference but
        semantically required for sell-side tracking.
        """
        self._open_positions.discard(f"{market_id}:{outcome}")

    @abstractmethod
    async def decide(self, observation: Observation) -> Decision:
        """Make a trading decision based on observation."""
        ...

    async def observe(self) -> Observation:
        """Fetch current market state.

        REF-001b: Sync tracked positions from API positions,
        ported from probablyprofit/agent/base.py:347-401.
        """
        markets = []
        positions = []
        balance = 0.0

        if self.client and hasattr(self.client, "get_markets"):
            markets = await self.client.get_markets(active=True, limit=50)
        if self.client and hasattr(self.client, "get_positions"):
            positions = await self.client.get_positions()
        if self.client and hasattr(self.client, "get_balance"):
            balance = await self.client.get_balance()

        # Sync tracked positions with actual positions (REF-001b)
        api_positions: set[str] = set()
        for pos in positions:
            mid = getattr(pos, "market_id", None) or getattr(pos, "asset_id", None) or ""
            outcome = getattr(pos, "outcome", "") or getattr(pos, "token_id", "") or ""
            size = getattr(pos, "size", 0) or getattr(pos, "balance", 0)
            if size > 0 and mid and outcome:
                api_positions.add(f"{mid}:{outcome}")
        if api_positions:
            self._open_positions.update(api_positions)

        obs = Observation(
            timestamp=datetime.now(),
            markets=markets,
            positions=positions,
            balance=balance,
        )
        await self.memory.add_observation(obs)
        return obs

    async def act(self, decision: Decision) -> bool:
        """Execute a trading decision.

        REF-001b: Position dedup via _has_position before buy,
        ported from probablyprofit/agent/base.py:420-574.
        """
        await self.memory.add_decision(decision)
        if decision.action == "hold":
            return True

        if decision.action == "buy":
            if not decision.market_id or not decision.outcome:
                return False
            # Skip if already have a position in this market/outcome
            if self._has_position(decision.market_id, decision.outcome):
                return True
            if self.dry_run:
                self._record_position(decision.market_id, decision.outcome)
                return True
            # Live execution — subclass overrides for actual placement
            self._record_position(decision.market_id, decision.outcome)
            return True

        if decision.action in ("sell", "close"):
            if not decision.market_id or not decision.outcome:
                return False
            if self.dry_run:
                self._discard_position(decision.market_id, decision.outcome)
                return True
            self._discard_position(decision.market_id, decision.outcome)
            return True

        # Unknown action
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
