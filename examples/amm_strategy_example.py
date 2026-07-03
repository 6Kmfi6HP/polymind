#!/usr/bin/env python3
"""
AMM Strategy Example
====================

Demonstrates the Polymind order-intent / executor pipeline in paper-trading
mode.  An AMM-style ladder places 4 limit orders around the mid-price of a
hypothetical market, then simulates a tick that crosses the spread so some
orders fill.

Usage::

    python examples/amm_strategy_example.py

Requirements: ``polymind`` (this project) installed or on PYTHONPATH.
"""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timezone

from polymind.core.intents import OrderIntent, OrderSide, StrategyIntent
from polymind.execution import (
    FillMode,
    FillModel,
    FillModelConfig,
    MarketSnapshot,
    PaperExecutor,
)

logger = logging.getLogger("amm_example")


# ── Helpers ───────────────────────────────────────────────────────────────────


def build_ladder(
    market_id: str,
    mid_price: float,
    spread_bps: float = 50,
    size: float = 100,
    levels: int = 4,
) -> list[OrderIntent]:
    """Create a symmetric ladder of limit orders around *mid_price*.

    Each level steps out by ``spread_bps`` basis points from mid.  Buy
    orders sit below mid, sell orders above mid, forming the classic
    "order book around the mid" pattern used by AMM-style strategies.

    Parameters
    ----------
    market_id:
        Polymarket CLOB market ID.
    mid_price:
        Current mid-price (centre point of the ladder).
    spread_bps:
        Gap between each ladder rung, in basis points (1 bp = 0.01 %).
    size:
        Token amount per order (same for each rung).
    levels:
        Number of rungs on each side of the ladder.

    Returns
    -------
    ``levels * 2`` order intents (``levels`` buys, ``levels`` sells).
    """
    step = spread_bps / 10_000.0
    orders: list[OrderIntent] = []

    for i in range(1, levels + 1):
        buy_price = round(mid_price * (1.0 - i * step), 6)
        orders.append(
            OrderIntent(
                market_id=market_id,
                side=OrderSide.BUY,
                price=buy_price,
                size=size,
                outcome="YES",
                metadata={"level": -i, "type": "ladder"},
            )
        )

    for i in range(1, levels + 1):
        sell_price = round(mid_price * (1.0 + i * step), 6)
        orders.append(
            OrderIntent(
                market_id=market_id,
                side=OrderSide.SELL,
                price=sell_price,
                size=size,
                outcome="YES",
                metadata={"level": i, "type": "ladder"},
            )
        )

    return orders


def print_status(executor: PaperExecutor) -> None:
    """Pretty-print open orders, positions, and cash."""
    print(f"\n{'=' * 60}")
    print(f"CASH: ${executor.cash:,.2f}  (initial: ${executor.initial_cash:,.2f})")
    print(f"OPEN ORDERS: {executor.get_open_order_count()}")
    print(f"{'=' * 60}")

    if executor.positions:
        print(f"\n{'POSITIONS':^60}")
        print(f"{'Market':<20} {'Outcome':<6} {'Size':>8} {'Avg Entry':>10}")
        print("-" * 60)
        for pos in executor.positions.values():
            print(
                f"{pos.market_id:<20} {pos.outcome:<6} {pos.size:>8.2f} " f"{pos.avg_entry:>10.6f}"
            )

    if executor.fills:
        print(f"\n{'FILLS':^60}")
        print(f"{'ID':<14} {'Side':<6} {'Price':>10} {'Size':>8} {'Fee':>8}")
        print("-" * 60)
        for f in executor.fills[-6:]:  # show last 6 fills
            print(
                f"{f.fill_id:<14} {f.side.value:<6} {f.price:>10.6f} "
                f"{f.size:>8.2f} {f.fee:>8.4f}"
            )

    if executor.orders:
        print(f"\n{'ORDERS':^60}")
        print(f"{'ID':<40} {'Side':<6} {'Price':>10} {'Size':>8} {'Status':<14}")
        print("-" * 60)
        for rec in executor.orders.values():
            print(
                f"{rec.identity.to_identity_string()[:38]:<40} "
                f"{rec.intent.side.value:<6} "
                f"{rec.intent.price:>10.6f} "
                f"{rec.intent.size:>8.2f} "
                f"{rec.status.name:<14}"
            )

    print()


# ── Async demo ────────────────────────────────────────────────────────────────


async def run_demo() -> None:
    """Execute a full AMM ladder scenario as an async demonstration.

    Steps
    -----
    1. Create a taker-mode FillModel (immediate fills when price crosses).
    2. Create a PaperExecutor with USD 10 000 initial capital.
    3. Build a 4-level buy/sell ladder around a $0.50 mid-price.
    4. Package the intents into a StrategyIntent and execute.
    5. Simulate a market-data tick that crosses the buy orders.
    6. Simulate a second tick that fills the first sell levels.
    7. Display final state (cash, positions, fills, open orders).
    """
    # ── 1. Fill model (taker mode: immediate fill at bid/ask) ────────────
    fill_config = FillModelConfig(
        mode=FillMode.TAKER,
        maker_fee_rate=0.0,
        taker_fee_rate=0.003,  # 0.3 % taker fee
        slippage_bps=5,  # 0.05 % additional slippage
    )
    fill_model = FillModel(config=fill_config)

    # ── 2. Paper executor with 10k starting cash ─────────────────────────
    executor = PaperExecutor(fill_model=fill_model, initial_cash=10_000.0)
    print_status(executor)

    MARKET_ID = "example-amm-market-001"

    # ── 3. Build ladder: mid = $0.50, 4 levels, 50 bp spacing ────────────
    ladder = build_ladder(
        market_id=MARKET_ID,
        mid_price=0.50,
        spread_bps=50,  # 0.50 % per rung
        size=100,
        levels=4,
    )
    print(f"Placing {len(ladder)} ladder orders around $0.50 mid-price ...\n")

    strategy_intent = StrategyIntent(
        timestamp=datetime.now(timezone.utc),
        strategy_name="amm_ladder_demo",
        orders=ladder,
    )

    # ── 4. Execute (place orders on the paper book) ──────────────────────
    # Without a MarketSnapshot, orders are registered open but not filled.
    result = await executor.execute(strategy_intent)
    print(f"Execute result: {result}\n")

    print("--- After placing ladder (no snapshot yet) ---")
    print_status(executor)

    # ── 5. Simulate a tick where ask drops below buy prices ──────────────
    # ask = 0.49 → buys at 0.4975, 0.4950, 0.4925, 0.4900 all >= 0.49
    # so they fill in TAKER mode.
    snapshot1 = MarketSnapshot(
        market_id=MARKET_ID,
        bid_price=0.48,
        bid_size=500,
        ask_price=0.49,
        ask_size=500,
        mid_price=0.485,
        timestamp=datetime.now(timezone.utc),
    )
    fills1 = await executor.simulate_tick(snapshot1)
    print(f"Tick 1 — ask = 0.49 → {fills1} buy fill(s)")
    print("--- After tick 1 ---")
    print_status(executor)

    # ── 6. Second tick: raise bid so sells fill ──────────────────────────
    # bid = 0.50 → sells at 0.5025, 0.5050 <= 0.50? No, 0.5025 > 0.50.
    # For a SELL to fill in taker mode, sell price <= bid.  Set bid higher.
    # Let's use bid = 0.51 so sells at 0.5025 and 0.5050 fill.
    snapshot2 = MarketSnapshot(
        market_id=MARKET_ID,
        bid_price=0.51,
        bid_size=500,
        ask_price=0.53,
        ask_size=500,
        mid_price=0.52,
        timestamp=datetime.now(timezone.utc),
    )
    fills2 = await executor.simulate_tick(snapshot2)
    print(f"Tick 2 — bid = 0.51 → {fills2} sell fill(s)")
    print("--- After tick 2 ---")
    print_status(executor)

    # ── 7. Cleanup ───────────────────────────────────────────────────────
    await executor.shutdown()
    print("Executor shut down cleanly.")


# ── Additional async pattern examples ────────────────────────────────────────


async def example_concurrent_ticks(executor: PaperExecutor, tick_count: int = 3) -> int:
    """Demonstrate concurrent snapshot simulation (example pattern).

    Parameters
    ----------
    executor:
        A PaperExecutor with some open orders.
    tick_count:
        Number of ticks to simulate concurrently.

    Returns
    -------
    Total number of fills across all ticks.
    """
    base_snapshot = MarketSnapshot(
        market_id="example-amm-market-001",
        bid_price=0.51,
        bid_size=500,
        ask_price=0.53,
        ask_size=500,
        mid_price=0.52,
        timestamp=datetime.now(timezone.utc),
    )

    async def run_tick(offset: int) -> int:
        snap = MarketSnapshot(
            market_id=base_snapshot.market_id,
            bid_price=base_snapshot.bid_price + offset * 0.01,
            bid_size=base_snapshot.bid_size,
            ask_price=base_snapshot.ask_price + offset * 0.01,
            ask_size=base_snapshot.ask_size,
            mid_price=(base_snapshot.bid_price + base_snapshot.ask_price) / 2 + offset * 0.01,
            timestamp=datetime.now(timezone.utc),
        )
        return await executor.simulate_tick(snap)

    tasks = [run_tick(i) for i in range(tick_count)]
    results = await asyncio.gather(*tasks)
    total = sum(results)
    logger.info("Concurrent ticks produced %d fills total", total)
    return total


async def example_cancel_all(executor: PaperExecutor, market_id: str) -> dict:
    """Demonstrate cancelling all orders for a market (example pattern).

    This is how strategies replace their entire ladder after a price shift.

    Parameters
    ----------
    executor:
        PaperExecutor with open orders.
    market_id:
        Market whose orders should be cancelled.

    Returns
    -------
    The executor result dict.
    """
    from polymind.core.intents import CancelIntent, StrategyIntent

    cancel_intent = StrategyIntent(
        timestamp=datetime.now(timezone.utc),
        strategy_name="amm_ladder_demo",
        cancels=[CancelIntent(market_id=market_id, reason="price shift")],
    )
    return await executor.execute(cancel_intent)


# ── Entry point ──────────────────────────────────────────────────────────────


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%H:%M:%S",
    )
    asyncio.run(run_demo())


if __name__ == "__main__":
    main()
