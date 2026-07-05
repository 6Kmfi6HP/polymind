#!/usr/bin/env python3
"""
Factor backtest runner.

Evaluates factor strategies against historical market data. Supports
both single-run and iterative backtesting with configurable parameters.

Usage::

    # Run a momentum factor backtest with default settings
    python scripts/backtest_factor.py --factor momentum

    # Specify custom parameters
    python scripts/backtest_factor.py --factor momentum --lookback-days 60 --top-n 10

    # Run a volatility factor backtest
    python scripts/backtest_factor.py --factor volatility --initial-capital 5000
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone

from polymind.backtesting.factor_bt import FactorBacktestConfig, FactorBacktester
from polymind.execution.fill_model import MarketSnapshot


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Factor backtest runner")
    parser.add_argument(
        "--factor",
        type=str,
        default="momentum",
        choices=["momentum", "volatility"],
        help="Factor signal to backtest (default: momentum)",
    )
    parser.add_argument(
        "--initial-capital",
        type=float,
        default=10000.0,
        help="Starting capital (default: 10000)",
    )
    parser.add_argument(
        "--lookback-days",
        type=int,
        default=30,
        help="Historical lookback in days (default: 30)",
    )
    parser.add_argument(
        "--top-n",
        type=int,
        default=5,
        help="Number of top markets to hold (default: 5)",
    )
    parser.add_argument(
        "--max-position-size",
        type=float,
        default=1000.0,
        help="Maximum capital per position (default: 1000)",
    )
    parser.add_argument(
        "--rebal-freq-hours",
        type=int,
        default=4,
        help="Rebalance frequency in hours (default: 4)",
    )
    parser.add_argument(
        "--format",
        type=str,
        default="text",
        choices=["text", "json"],
        help="Output format (default: text)",
    )
    parser.add_argument(
        "--snapshots",
        type=str,
        default=None,
        help="Path to JSONL snapshots file (default: demo mode with synthetic data)",
    )
    return parser.parse_args()


def _load_snapshots(path: str) -> list[MarketSnapshot]:
    """Load market snapshots from a JSONL file."""
    snapshots: list[MarketSnapshot] = []
    with open(path) as f:
        for line in f:
            data = json.loads(line.strip())
            snapshots.append(
                MarketSnapshot(
                    market_id=data.get("market_id", ""),
                    timestamp=datetime.fromisoformat(
                        data.get("timestamp", datetime.now(timezone.utc).isoformat())
                    ),
                    bid_price=float(data.get("bid_price", 0.0)),
                    ask_price=float(data.get("ask_price", 0.0)),
                    mid_price=float(data.get("mid_price", data.get("price", 0.0))),
                    bid_size=float(data.get("bid_size", 0.0)),
                    ask_size=float(data.get("ask_size", 0.0)),
                )
            )
    return snapshots


def _generate_demo_data() -> tuple[list[dict[str, float]], list[dict[str, MarketSnapshot]]]:
    """Generate synthetic scores and snapshots for demo/quick-start.

    Returns a list of (scores, snapshots) pairs, one per time step.
    """
    import random

    random.seed(42)
    market_ids = [f"0xdemomkt{i}" for i in range(5)]
    steps: list[tuple[dict[str, float], dict[str, MarketSnapshot]]] = []

    base_time = datetime.now(timezone.utc)
    for _step in range(20):
        scores: dict[str, float] = {}
        snaps: dict[str, MarketSnapshot] = {}
        for mid in market_ids:
            scores[mid] = random.uniform(-1.0, 1.0)
            mid_price = 0.50 + random.uniform(-0.05, 0.05)
            snaps[mid] = MarketSnapshot(
                market_id=mid,
                timestamp=base_time,
                bid_price=mid_price - 0.05,
                ask_price=mid_price + 0.05,
                mid_price=mid_price,
                bid_size=random.uniform(500, 5000),
                ask_size=random.uniform(500, 5000),
            )
        steps.append((scores, snaps))
    return steps


def main() -> None:
    args = _parse_args()

    config = FactorBacktestConfig(
        initial_capital=args.initial_capital,
        lookback_days=args.lookback_days,
        top_n=args.top_n,
        max_position_size=args.max_position_size,
        rebal_freq_hours=args.rebal_freq_hours,
    )

    backtester = FactorBacktester(config=config)

    if args.snapshots:
        snapshots = _load_snapshots(args.snapshots)
        # When loading from file, derive scores from bid-ask spread
        steps: list[tuple[dict[str, float], dict[str, MarketSnapshot]]] = [
            (
                {snap.market_id: 1.0},
                {snap.market_id: snap},
            )
            for snap in snapshots
        ]
    else:
        print("[info] No --snapshots provided; using synthetic demo data", file=sys.stderr)
        steps = _generate_demo_data()

    # Run backtest step by step
    final_result = None
    for scores, snaps in steps:
        result = backtester.run(scores=scores, snapshots=snaps)
        final_result = result

    if args.format == "json":
        output = {
            "factor": args.factor,
            "trades": final_result.total_trades if final_result else 0,
            "win_rate": final_result.win_rate if final_result else 0.0,
            "sharpe": final_result.sharpe if final_result else 0.0,
            "sortino": final_result.sortino if final_result else 0.0,
            "max_drawdown": final_result.max_drawdown if final_result else 0.0,
            "total_return": final_result.total_return if final_result else 0.0,
        }
        print(json.dumps(output, indent=2))
    else:
        if final_result is None:
            print("[error] No snapshots processed")
            sys.exit(1)
        print(f"\n=== Factor Backtest: {args.factor} ===")
        print(f"  Trades:        {final_result.total_trades}")
        print(f"  Win Rate:      {final_result.win_rate:.1%}")
        print(f"  Sharpe:        {final_result.sharpe:.3f}")
        print(f"  Sortino:       {final_result.sortino:.3f}")
        print(f"  Max Drawdown:  {final_result.max_drawdown:.2%}")
        print(f"  Total Return:  ${final_result.total_return:.2f}")
        print()


if __name__ == "__main__":
    main()
