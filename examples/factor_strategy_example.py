"""
Factor Strategy Example — end-to-end factor pipeline demo.

Demonstrates:
1. Creating MarketSnapshot data (raw market data)
2. Building a UniverseSnapshot and computing factor scores
3. Converting scores into PortfolioTargets via portfolio construction
4. Using FactorExecutionBridge to create OrderIntents
5. Creating CancelIntents for rebalancing

Run: python3 examples/factor_strategy_example.py
"""

from __future__ import annotations

import asyncio
from datetime import datetime

from polymind.core.intents import OrderIntent, StrategyIntent
from polymind.core.portfolio import PortfolioTarget
from polymind.execution.fill_model import FillMode, FillModel, FillModelConfig, MarketSnapshot
from polymind.factors.execution import ExecutionBridgeConfig, FactorExecutionBridge
from polymind.factors.pipeline import MarketFeatures, UniverseSnapshot
from polymind.factors.portfolio_construction import PortfolioConfig, construct_portfolio
from polymind.factors.scoring import momentum_score, rank_normalize


async def main() -> None:
    print("=" * 64)
    print("Factor Strategy Example — End-to-End Pipeline Demo")
    print("=" * 64)

    # ── 1. Create MarketSnapshot data ──────────────────────────────────────
    # In production these come from the exchange; here we build them by hand.
    now = datetime.now()

    snapshots = {
        "0xaaa": MarketSnapshot(
            market_id="0xaaa",
            bid_price=0.45,
            bid_size=2000.0,
            ask_price=0.46,
            ask_size=1800.0,
            mid_price=0.455,
            timestamp=now,
        ),
        "0xbbb": MarketSnapshot(
            market_id="0xbbb",
            bid_price=0.72,
            bid_size=1500.0,
            ask_price=0.74,
            ask_size=1200.0,
            mid_price=0.73,
            timestamp=now,
        ),
        "0xccc": MarketSnapshot(
            market_id="0xccc",
            bid_price=0.30,
            bid_size=3000.0,
            ask_price=0.32,
            ask_size=2800.0,
            mid_price=0.31,
            timestamp=now,
        ),
        "0xddd": MarketSnapshot(
            market_id="0xddd",
            bid_price=0.88,
            bid_size=800.0,
            ask_price=0.90,
            ask_size=700.0,
            mid_price=0.89,
            timestamp=now,
        ),
        "0xeee": MarketSnapshot(
            market_id="0xeee",
            bid_price=0.10,
            bid_size=5000.0,
            ask_price=0.12,
            ask_size=4500.0,
            mid_price=0.11,
            timestamp=now,
        ),
    }

    print("\n── 1. Market Snapshots ──")
    for mid, s in snapshots.items():
        print(f"  {mid}: bid={s.bid_price:.2f}  ask={s.ask_price:.2f}  mid={s.mid_price:.3f}")

    # ── 2. Compute factor scores ───────────────────────────────────────────
    # Build a UniverseSnapshot with MarketFeatures for each market.
    # The features (momentum, spread, volume) represent derived signals.
    features = {
        "0xaaa": MarketFeatures(
            market_id="0xaaa",
            mid_price=0.455,
            spread_bps=22.0,
            volume_24h=50_000.0,
            momentum_24h=0.12,  # positive momentum
            volatility_24h=0.15,
        ),
        "0xbbb": MarketFeatures(
            market_id="0xbbb",
            mid_price=0.73,
            spread_bps=27.0,
            volume_24h=35_000.0,
            momentum_24h=0.08,
            volatility_24h=0.10,
        ),
        "0xccc": MarketFeatures(
            market_id="0xccc",
            mid_price=0.31,
            spread_bps=65.0,
            volume_24h=12_000.0,
            momentum_24h=-0.05,  # negative momentum
            volatility_24h=0.40,
        ),
        "0xddd": MarketFeatures(
            market_id="0xddd",
            mid_price=0.89,
            spread_bps=22.0,
            volume_24h=8_000.0,
            momentum_24h=0.21,  # strongest positive momentum
            volatility_24h=0.08,
        ),
        "0xeee": MarketFeatures(
            market_id="0xeee",
            mid_price=0.11,
            spread_bps=180.0,
            volume_24h=2_000.0,  # wide spread, low volume
            momentum_24h=-0.15,  # strongest negative momentum
            volatility_24h=0.60,
        ),
    }

    universe = UniverseSnapshot(timestamp=now, markets=features)

    # Score: higher momentum = more attractive
    raw_scores = momentum_score(universe, lookback="24h")
    print("\n── 2a. Raw Momentum Scores ──")
    for mid in sorted(raw_scores, key=raw_scores.get, reverse=True):
        print(f"  {mid}: {raw_scores[mid]:+.4f}")

    # Normalise scores to percentile ranks (0.0 – 1.0)
    ranked = rank_normalize(raw_scores)
    print("\n── 2b. Rank-Normalised Scores (0=worst, 1=best) ──")
    for mid in sorted(ranked, key=ranked.get, reverse=True):
        print(f"  {mid}: {ranked[mid]:.3f}")

    # ── 3. Construct PortfolioTargets from scores ──────────────────────────
    config = PortfolioConfig(
        top_n=3,
        max_exposure_per_market=200.0,
        total_exposure=500.0,
        min_confidence=0.1,
    )
    targets: list[PortfolioTarget] = construct_portfolio(raw_scores, config)

    print("\n── 3. Portfolio Targets ──")
    for t in targets:
        print(
            f"  {t.market_id}: {t.direction.name:6s}  size={t.target_size:.1f}  "
            f"conf={t.confidence:.2f}  rank={t.rank}  reason={t.reason}"
        )

    # ── 4. Convert PortfolioTargets → OrderIntents via FactorExecutionBridge
    bridge = FactorExecutionBridge(ExecutionBridgeConfig(max_position_size=500.0))

    # Use the first market's snapshot for price-aware sizing (or whichever
    # snapshot matches each target — here we reuse a generic snapshot).
    snapshot = snapshots["0xaaa"]

    all_orders: list[OrderIntent] = []
    print("\n── 4. Order Intents (via FactorExecutionBridge) ──")
    for target in targets:
        orders = await bridge.to_order_intents(target, snapshot, available_cash=10_000.0)
        all_orders.extend(orders)
        direction = "LONG" if orders and orders[0].side.value == "BUY" else "SHORT"
        if orders:
            print(
                f"  {target.market_id}: {direction}  {orders[0].size:.1f}  "
                f"slippage={orders[0].metadata['slippage_bps']}bps"
            )

    # ── 5. (Optional) Execute through PaperExecutor ────────────────────────
    from polymind.execution.executor import PaperExecutor

    executor = PaperExecutor(
        fill_model=FillModel(FillModelConfig(mode=FillMode.TAKER)),
        initial_cash=10_000.0,
    )
    intent = StrategyIntent(
        timestamp=now,
        strategy_name="factor-momentum",
        orders=all_orders,
    )
    print(f"\n── 5. Executing {len(all_orders)} order(s) via PaperExecutor ──")
    result = await executor.execute(intent)
    print(f"  Result keys: {list(result.keys())}")
    print(f"  Cash remaining: ${executor.cash:.2f}")
    for fill in executor.fills:
        print(f"  Fill: {fill.side} {fill.size:.1f} @ ${fill.price:.4f}")

    # ── 6. Create CancelIntents for rebalancing ────────────────────────────
    # Markets to cancel: the current holdings we want to exit.
    current_holdings = [t.market_id for t in targets]
    cancels = await bridge.to_cancel_intents(current_holdings)

    print("\n── 6. Cancel Intents for Rebalancing ──")
    for c in cancels:
        print(f"  Cancel all orders on {c.market_id} (reason: {c.reason})")

    print("\n✅ Factor strategy example completed successfully!")


if __name__ == "__main__":
    asyncio.run(main())
