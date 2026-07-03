"""
Factor Strategy Example — factor execution bridge demo.

Demonstrates:
1. Creating PortfolioTargets from factor signals
2. Using FactorExecutionBridge to create OrderIntents
3. Executing through PaperExecutor
4. Cancelling stale positions for rebalancing

Run: python3 examples/factor_strategy_example.py
"""

from __future__ import annotations

import asyncio
from datetime import datetime

from polymind.core.intents import OrderIntent, OrderSide, StrategyIntent
from polymind.core.portfolio import PortfolioTarget, PositionDirection
from polymind.execution.executor import PaperExecutor
from polymind.execution.fill_model import FillModel, FillModelConfig, FillMode, MarketSnapshot
from polymind.factors.execution import ExecutionBridgeConfig, FactorExecutionBridge


async def main() -> None:
    print("=" * 60)
    print("Factor Strategy Example — Execution Bridge Demo")
    print("=" * 60)

    # 1. Create market snapshot
    snapshot = MarketSnapshot(
        market_id="0xabc",
        bid_price=0.50,
        bid_size=1000.0,
        ask_price=0.51,
        ask_size=1000.0,
        mid_price=0.505,
        timestamp=datetime.now(),
    )
    print(f"\nMarket: 0xabc | Bid: {snapshot.bid_price} | Ask: {snapshot.ask_price}")

    # 2. Create factor portfolio targets
    targets = [
        PortfolioTarget(
            market_id="0xabc",
            direction=PositionDirection.LONG,
            target_size=100.0,
            confidence=0.85,
            rank=1,
            reason="momentum-7d",
        ),
        PortfolioTarget(
            market_id="0xdef",
            direction=PositionDirection.SHORT,
            target_size=50.0,
            confidence=0.72,
            rank=2,
            reason="volatility-breakout",
        ),
    ]

    # 3. Convert to order intents via bridge
    bridge = FactorExecutionBridge(ExecutionBridgeConfig(max_position_size=500.0))
    print(f"\nConverting {len(targets)} portfolio targets to order intents...")

    all_orders: list[OrderIntent] = []
    for target in targets:
        orders = await bridge.to_order_intents(target, snapshot)
        all_orders.extend(orders)
        print(f"  {target.reason}: {target.direction.name} {target.target_size:.0f} → {len(orders)} order(s)")

    # 4. Execute through paper executor
    executor = PaperExecutor(
        fill_model=FillModel(FillModelConfig(mode=FillMode.TAKER)),
        initial_cash=10_000.0,
    )
    intent = StrategyIntent(
        timestamp=datetime.now(),
        strategy_name="factor-example",
        orders=all_orders,
    )
    print(f"\nExecuting {len(all_orders)} orders...")
    result = await executor.execute(intent)
    print(f"Execute result keys: {list(result.keys())}")

    # 5. Check results
    print(f"\nCash remaining: ${executor.cash:.2f}")
    print(f"Fills recorded: {len(executor.fills)}")
    for fill in executor.fills:
        print(f"  Fill: {fill.side} {fill.size:.1f} @ ${fill.price:.4f}")

    # 6. Cancel stale positions for rebalance
    cancels = await bridge.to_cancel_intents(["0xabc", "0xdef"])
    print(f"\nCreated {len(cancels)} cancel intents for rebalancing")
    for c in cancels:
        print(f"  Cancel: {c.market_id} ({c.reason})")

    print("\n✅ Factor strategy example completed successfully!")


if __name__ == "__main__":
    asyncio.run(main())
