#!/usr/bin/env python3
"""
Factor data collection daemon.

Continuously polls the Polymarket Data API and persists CLOB snapshots
to the PriceStore. Designed to run as a background process (cron, systemd)
or interactively.

Usage::

    # Run once (single poll cycle)
    python scripts/collect_snapshots.py --once

    # Continuous collection (default 60s interval)
    python scripts/collect_snapshots.py --interval 120

    # Specify output path for the price store
    python scripts/collect_snapshots.py --store /path/to/snapshots.jsonl
"""

from __future__ import annotations

import argparse
import asyncio
import contextlib
import logging
import signal
import sys

from polymind.data.collector import CollectorConfig, SnapshotCollector
from polymind.polymarket.data_api import PolymarketDataAPI
from polymind.storage.price_store import PriceStore
from polymind.utils.logging import LogConfig, setup_logging

logger = logging.getLogger("collect-snapshots")


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Factor data collection daemon")
    parser.add_argument(
        "--once",
        action="store_true",
        help="Run a single poll cycle and exit",
    )
    parser.add_argument(
        "-i",
        "--interval",
        type=int,
        default=60,
        help="Poll interval in seconds (default: 60)",
    )
    parser.add_argument(
        "--store",
        type=str,
        default=None,
        help="Path to the price store file (default: in-memory)",
    )
    parser.add_argument(
        "--max-markets",
        type=int,
        default=50,
        help="Maximum number of markets to poll per cycle (default: 50)",
    )
    parser.add_argument(
        "--log-file",
        type=str,
        default=None,
        help="Log file path (default: stdout)",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level (default: INFO)",
    )
    return parser.parse_args()


async def _main() -> None:
    args = _parse_args()

    setup_logging(
        LogConfig(
            name="collect-snapshots",
            level=args.log_level,
            log_file=args.log_file,
        )
    )

    config = CollectorConfig(
        poll_interval=float(args.interval),
        max_markets=args.max_markets,
    )

    api = PolymarketDataAPI()
    store = PriceStore(path=args.store or ":memory:")
    collector = SnapshotCollector(api=api, store=store, config=config)

    await store.connect()

    def _shutdown() -> None:
        logger.info("Shutdown signal received, stopping...")
        asyncio.ensure_future(collector.stop())

    loop = asyncio.get_event_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        with contextlib.suppress(NotImplementedError):
            loop.add_signal_handler(sig, _shutdown)

    try:
        if args.once:
            logger.info("Running single poll cycle...")
            count = await collector.run_once()
            logger.info("Collected %d snapshots", count)
        else:
            logger.info(
                "Starting continuous collection (interval=%ds, max_markets=%d)...",
                args.interval,
                args.max_markets,
            )
            task = asyncio.create_task(collector.run_forever())
            await task
    except asyncio.CancelledError:
        logger.info("Collection cancelled")
    finally:
        await store.close()
        logger.info("Collection stopped")


if __name__ == "__main__":
    sys.exit(asyncio.run(_main()))
