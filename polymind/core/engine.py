"""
TradingEngine — central orchestrator for strategy → risk → execution pipeline.

Connects a market-making strategy, workflow runner, risk gates, and executor
into a single observe-decide-act loop.
"""

from __future__ import annotations

import asyncio
from collections.abc import Callable
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any

from polymind.core.intents import IntentExecutor
from polymind.core.risk import RiskContext, RiskGate
from polymind.core.strategy import BaseMMStrategy
from polymind.execution.fill_model import MarketSnapshot
from polymind.workflows.runner import WorkflowRunner


@dataclass
class TradingEngineConfig:
    """Configuration for the TradingEngine.

    Parameters
    ----------
    strategy_name:
        Name of the strategy to run (for reporting).
    loop_interval:
        Seconds between observe-decide-act ticks.
    dry_run:
        If True, executor runs in simulation mode.
    """

    strategy_name: str = ""
    loop_interval: float = 60.0
    dry_run: bool = True


@dataclass
class TickResult:
    """Outcome of a single observe-decide-act tick."""

    timestamp: datetime
    strategy: str
    orders_proposed: int
    cancels_proposed: int
    orders_placed: int = 0
    orders_cancelled: int = 0
    risk_approved: bool = True
    error: str = ""
    execution_ms: float = 0.0


class TradingEngine:
    """Central runtime that wires strategy → risk → executor → workflow.

    Usage::

        engine = TradingEngine(strategy, executor, runner, config)
        snapshot = MarketSnapshot(...)
        result = await engine.run_tick(snapshot)
        await engine.run_forever(snapshot_provider)
        await engine.stop()
    """

    def __init__(
        self,
        strategy: BaseMMStrategy,
        executor: IntentExecutor,
        runner: WorkflowRunner | None = None,
        risk_manager: RiskGate | None = None,
        config: TradingEngineConfig | None = None,
    ) -> None:
        self._strategy = strategy
        self._executor = executor
        self._runner = runner
        self._risk_manager = risk_manager
        self._config = config or TradingEngineConfig(
            strategy_name=strategy.name,
        )
        self._running = False
        self._task: asyncio.Task[Any] | None = None
        self._last_result: TickResult | None = None
        self._total_orders: int = 0
        self._total_ticks: int = 0

    async def run_tick(self, market: MarketSnapshot) -> TickResult:
        """Execute one observe-decide-act cycle.

        Parameters
        ----------
        market:
            Current market snapshot to analyze.

        Returns
        -------
        TickResult
            Outcome of the tick.
        """
        import time

        start = time.monotonic()
        now = datetime.now(timezone.utc)
        self._total_ticks += 1

        try:
            intent = await self._strategy.analyze(market)
        except Exception as exc:
            result = TickResult(
                timestamp=now,
                strategy=self._config.strategy_name,
                orders_proposed=0,
                cancels_proposed=0,
                error=f"Strategy analysis failed: {exc}",
                execution_ms=(time.monotonic() - start) * 1000,
            )
            self._last_result = result
            return result

        if intent is None or intent.is_empty():
            result = TickResult(
                timestamp=now,
                strategy=self._config.strategy_name,
                orders_proposed=0,
                cancels_proposed=0,
                execution_ms=(time.monotonic() - start) * 1000,
            )
            self._last_result = result
            return result

        # Risk gate
        if self._risk_manager is not None:
            context = RiskContext(
                current_positions={},
                current_exposure=0.0,
                daily_pnl=0.0,
                is_kill_switch_active=False,
                portfolio_value=0.0,
            )
            decision = await self._risk_manager.evaluate(intent, context)
            if not decision.approved:
                result = TickResult(
                    timestamp=now,
                    strategy=self._config.strategy_name,
                    orders_proposed=len(intent.orders),
                    cancels_proposed=len(intent.cancels),
                    risk_approved=False,
                    error=decision.reason or "Risk gate rejected",
                    execution_ms=(time.monotonic() - start) * 1000,
                )
                self._last_result = result
                return result

        # Execute
        try:
            exec_result = await self._executor.execute(intent)
        except Exception as exc:
            result = TickResult(
                timestamp=now,
                strategy=self._config.strategy_name,
                orders_proposed=len(intent.orders),
                cancels_proposed=len(intent.cancels),
                error=f"Execution failed: {exc}",
                execution_ms=(time.monotonic() - start) * 1000,
            )
            self._last_result = result
            return result

        orders_placed = 0
        orders_cancelled = 0
        if isinstance(exec_result, dict):
            for entry in exec_result.values():
                if isinstance(entry, dict):
                    if entry.get("status") in ("OPEN", "FILLED", "PARTIALLY_FILLED"):
                        orders_placed += 1
                    if entry.get("status") == "CANCELLED":
                        orders_cancelled += 1

        self._total_orders += orders_placed

        result = TickResult(
            timestamp=now,
            strategy=self._config.strategy_name,
            orders_proposed=len(intent.orders),
            cancels_proposed=len(intent.cancels),
            orders_placed=orders_placed,
            orders_cancelled=orders_cancelled,
            risk_approved=True,
            execution_ms=(time.monotonic() - start) * 1000,
        )
        self._last_result = result
        return result

    async def run_tick_all(self, markets: list[MarketSnapshot]) -> list[TickResult]:
        """Execute one observe-decide-act cycle over *all* filtered markets.

        Parameters
        ----------
        markets:
            All available market snapshots.  The strategy's **filter_markets**
            method is called first, then **analyze** is run on each filtered
            market.

        Returns
        -------
        list[TickResult]
            One result per market that passed the filter.
        """
        filtered = self._strategy.filter_markets(markets)
        results: list[TickResult] = []
        for m in filtered:
            r = await self.run_tick(m)
            results.append(r)
        return results

    async def run_forever(
        self,
        market_provider: Callable[[], Awaitable[MarketSnapshot]],
    ) -> None:
        """Run observe-decide-act ticks in a loop until stopped.

        Parameters
        ----------
        market_provider:
            Async callable that returns the current MarketSnapshot.
        """
        self._running = True
        while self._running:
            try:
                market = await market_provider()
                await self.run_tick(market)
            except asyncio.CancelledError:
                break
            except Exception:
                pass
            await asyncio.sleep(self._config.loop_interval)

    def start_background(
        self,
        market_provider: Callable[[], Awaitable[MarketSnapshot]],
    ) -> asyncio.Task[Any]:
        """Start ``run_forever`` as a background task."""
        self._task = asyncio.create_task(self.run_forever(market_provider))
        return self._task

    async def stop(self) -> None:
        """Signal the trading loop to stop."""
        self._running = False
        if self._task is not None:
            self._task.cancel()
            from contextlib import suppress

            with suppress(asyncio.CancelledError, Exception):
                await self._task
            self._task = None

    def status(self) -> dict[str, Any]:
        """Return a summary of the engine's current state."""
        return {
            "strategy": self._config.strategy_name,
            "running": self._running,
            "dry_run": self._config.dry_run,
            "total_ticks": self._total_ticks,
            "total_orders": self._total_orders,
            "last_tick": self._last_result,
        }


from collections.abc import Awaitable  # noqa: E402
