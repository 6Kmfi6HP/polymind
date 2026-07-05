"""
Feature computation for the factor pipeline.

Provides functions and a :class:`FeatureComputer` class that compute
market features from raw CLOB snapshot data. Features include micro-price,
weighted mid, depth imbalance, momentum, and volatility.

Usage::

    computer = FeatureComputer(window=24)
    mf = computer.compute(
        market_id="0xm1",
        bid_price=0.45,
        ask_price=0.55,
        bid_size=1000.0,
        ask_size=2000.0,
        volume_24h=50000.0,
    )
    universe = computer.compute_universe(raw_snapshots)
"""

from __future__ import annotations

import math
from collections import defaultdict
from datetime import datetime, timezone
from typing import TYPE_CHECKING, Any

if TYPE_CHECKING:
    from polymind.factors.pipeline import MarketFeatures, UniverseSnapshot


def compute_spread_bps(bid_price: float, ask_price: float) -> float:
    """Compute the bid-ask spread in basis points.

    Args:
        bid_price: Best bid price (must be >= 0).
        ask_price: Best ask price (must be >= bid_price).

    Returns:
        Spread in basis points, or ``inf`` if mid price is zero.

    Raises:
        ValueError: If prices are negative or bid > ask.
    """
    if bid_price < 0 or ask_price < 0:
        raise ValueError("Prices must be non-negative")
    if bid_price > ask_price:
        raise ValueError("bid_price must be less than or equal to ask_price")

    mid = (bid_price + ask_price) / 2.0
    if mid <= 0:
        return float("inf")
    return (ask_price - bid_price) / mid * 10_000


def compute_micro_price(
    bid_price: float,
    ask_price: float,
    bid_size: float,
    ask_size: float,
) -> float:
    """Compute the micro-price (volume-weighted price).

    The micro-price weights bid and ask by their liquidity depth,
    giving a more stable reference price than the simple midpoint.

    Formula::

        micro_price = (bid_price * ask_size + ask_price * bid_size)
                      / (bid_size + ask_size)

    When both sizes are zero, falls back to the simple midpoint.

    Args:
        bid_price: Best bid price.
        ask_price: Best ask price.
        bid_size: Size at the best bid.
        ask_size: Size at the best ask.

    Returns:
        The micro-price.
    """
    total_size = bid_size + ask_size
    if total_size <= 0:
        return (bid_price + ask_price) / 2.0
    return (bid_price * ask_size + ask_price * bid_size) / total_size


def compute_weighted_mid(
    bid_price: float,
    ask_price: float,
    bid_size: float,
    ask_size: float,
) -> float:
    """Compute a liquidity-weighted mid price.

    Similar to micro-price but weights the bid and ask prices directly
    by their own sizes::

        weighted_mid = (bid_price * bid_size + ask_price * ask_size)
                       / (bid_size + ask_size)

    Falls back to the simple midpoint when both sizes are zero.

    Args:
        bid_price: Best bid price.
        ask_price: Best ask price.
        bid_size: Size at the best bid.
        ask_size: Size at the best ask.

    Returns:
        The weighted mid price.
    """
    total_size = bid_size + ask_size
    if total_size <= 0:
        return (bid_price + ask_price) / 2.0
    return (bid_price * bid_size + ask_price * ask_size) / total_size


def compute_depth_imbalance(bid_size: float, ask_size: float) -> float:
    """Compute the order-book depth imbalance.

    Returns a value in [-1, 1] where:

    - **1** = entirely bid-heavy (no ask liquidity)
    - **0** = perfectly balanced
    - **-1** = entirely ask-heavy (no bid liquidity)

    Formula::

        imbalance = (bid_size - ask_size) / (bid_size + ask_size)

    When both sizes are zero, returns 0.

    Args:
        bid_size: Size at the best bid.
        ask_size: Size at the best ask.

    Returns:
        Depth imbalance in [-1, 1].
    """
    total = bid_size + ask_size
    if total <= 0:
        return 0.0
    return (bid_size - ask_size) / total


def momentum_from_history(
    prices: list[float],
    lookback: int,
) -> float | None:
    """Compute momentum from a price history series.

    Momentum is the rate of change over the lookback window::

        momentum = (current_price - price_{lookback}) / price_{lookback}

    Returns ``None`` if insufficient history exists.

    Args:
        prices: Historical prices in chronological order.
        lookback: Number of periods to look back (must be >= 1).

    Returns:
        Momentum as a decimal fraction, or ``None``.
    """
    if lookback < 1 or len(prices) < lookback + 1:
        return None
    current = prices[-1]
    past = prices[-(lookback + 1)]
    if past == 0:
        return None
    return (current - past) / past


def volatility_from_history(
    prices: list[float],
    lookback: int | None = None,
) -> float | None:
    """Compute volatility from a price history series.

    Volatility is the standard deviation of log returns over the window.
    Returns ``None`` if fewer than 2 prices are available.

    Args:
        prices: Historical prices in chronological order.
        lookback: Number of periods to use (default: all available).

    Returns:
        Volatility as a decimal fraction, or ``None``.
    """
    if len(prices) < 2:
        return None

    window = prices[-(lookback or len(prices)) :] if lookback else prices
    if len(window) < 2:
        return None

    log_returns: list[float] = []
    for i in range(1, len(window)):
        if window[i - 1] > 0 and window[i] > 0:
            log_returns.append(math.log(window[i] / window[i - 1]))

    if len(log_returns) < 1:
        return None

    mean = sum(log_returns) / len(log_returns)
    variance = sum((r - mean) ** 2 for r in log_returns) / len(log_returns)
    return math.sqrt(variance)


class FeatureComputer:
    """Computes market features from raw snapshot data.

    Maintains per-market price history for momentum and volatility
    calculations. Call :meth:`compute` for each new snapshot, or
    :meth:`compute_universe` for bulk processing.

    Usage::

        computer = FeatureComputer(window=24)
        for snapshot in snapshots:
            mf = computer.compute(**snapshot)
            # mf is a MarketFeatures with all fields populated
    """

    def __init__(self, window: int = 24) -> None:
        """Initialize the feature computer.

        Args:
            window: Maximum number of history entries to keep per market.
        """
        self.window = window
        self._history: dict[str, list[float]] = defaultdict(list)

    @property
    def history(self) -> dict[str, list[float]]:
        """Raw price history per market (read-only)."""
        return dict(self._history)

    def compute(
        self,
        market_id: str,
        bid_price: float,
        ask_price: float,
        bid_size: float,
        ask_size: float,
        volume_24h: float = 0.0,
        timestamp: datetime | None = None,
    ) -> MarketFeatures:
        """Compute features for a single market snapshot.

        Args:
            market_id: Market identifier.
            bid_price: Best bid price.
            ask_price: Best ask price.
            bid_size: Size at the best bid.
            ask_size: Size at the best ask.
            volume_24h: 24-hour volume (optional).
            timestamp: Snapshot timestamp (defaults to now).

        Returns:
            A :class:`MarketFeatures` instance with all computed fields.
        """
        # Avoid circular import at runtime by importing here
        from polymind.factors.pipeline import MarketFeatures

        mid = (bid_price + ask_price) / 2.0
        spread = compute_spread_bps(bid_price, ask_price)
        micro_price = compute_micro_price(bid_price, ask_price, bid_size, ask_size)
        weighted_mid = compute_weighted_mid(bid_price, ask_price, bid_size, ask_size)
        imbalance = compute_depth_imbalance(bid_size, ask_size)

        # Update history for this market
        self._history[market_id].append(mid)
        if len(self._history[market_id]) > self.window:
            self._history[market_id].pop(0)

        prices = self._history[market_id]

        # Compute momentum at multiple lookbacks
        n = len(prices)
        mom_4h = momentum_from_history(prices, lookback=min(4, n - 1)) if n >= 2 else None
        mom_24h = momentum_from_history(prices, lookback=min(24, n - 1)) if n >= 2 else None
        mom_7d = momentum_from_history(prices, lookback=min(168, n - 1)) if n >= 2 else None
        vol_24h = volatility_from_history(prices) if n >= 2 else None

        return MarketFeatures(
            market_id=market_id,
            mid_price=mid,
            spread_bps=spread,
            volume_24h=volume_24h,
            momentum_4h=mom_4h,
            momentum_24h=mom_24h,
            momentum_7d=mom_7d,
            volatility_24h=vol_24h,
            additional={
                "micro_price": micro_price,
                "weighted_mid": weighted_mid,
                "depth_imbalance": imbalance,
            },
        )

    def compute_universe(
        self,
        raw_data: dict[str, dict[str, float]],
        timestamp: datetime | None = None,
    ) -> UniverseSnapshot:
        """Compute features for all markets in a raw data dict.

        Args:
            raw_data: Dict of ``market_id -> {bid, ask, bid_size, ask_size, volume}``.
            timestamp: Snapshot timestamp (defaults to now).

        Returns:
            A :class:`UniverseSnapshot` with computed features.
        """
        from polymind.factors.pipeline import UniverseSnapshot

        ts = timestamp or datetime.now(timezone.utc)
        markets: dict[str, Any] = {}

        for mid, data in raw_data.items():
            mf = self.compute(
                market_id=mid,
                bid_price=data.get("bid", 0.0),
                ask_price=data.get("ask", 0.0),
                bid_size=data.get("bid_size", 0.0),
                ask_size=data.get("ask_size", 0.0),
                volume_24h=data.get("volume", 0.0),
                timestamp=ts,
            )
            markets[mid] = mf

        return UniverseSnapshot(timestamp=ts, markets=markets)

    def clear_history(self, market_id: str | None = None) -> None:
        """Clear price history for one or all markets.

        Args:
            market_id: If provided, clear only this market's history.
                      Otherwise, clear all history.
        """
        if market_id is not None:
            self._history.pop(market_id, None)
        else:
            self._history.clear()
