"""
Tradability filters for the factor pipeline.

Each filter checks a specific dimension. Filters are composable:
combine them to reject markets that fail any check.
"""

from __future__ import annotations

from dataclasses import dataclass

from polymind.factors.pipeline import UniverseSnapshot


@dataclass
class FilterConfig:
    """Configuration for tradability filters."""

    max_spread_bps: float = 100.0  # max bid-ask spread (1%)
    min_volume_24h: float = 1000.0  # min 24h volume
    max_volatility_24h: float = 0.5  # max 24h volatility (50%)
    min_mid_price: float = 0.01  # min mid price


def filter_by_spread(
    universe: UniverseSnapshot,
    config: FilterConfig,
) -> UniverseSnapshot:
    """Remove markets with spread wider than max_spread_bps."""
    filtered = {
        mid: mf
        for mid, mf in universe.markets.items()
        if mf.spread_bps <= config.max_spread_bps
    }
    universe.markets = filtered
    return universe


def filter_by_volume(
    universe: UniverseSnapshot,
    config: FilterConfig,
) -> UniverseSnapshot:
    """Remove markets with 24h volume below min_volume_24h."""
    filtered = {
        mid: mf
        for mid, mf in universe.markets.items()
        if mf.volume_24h >= config.min_volume_24h
    }
    universe.markets = filtered
    return universe


def filter_by_volatility(
    universe: UniverseSnapshot,
    config: FilterConfig,
) -> UniverseSnapshot:
    """Remove markets with volatility above max_volatility_24h."""
    filtered = {
        mid: mf
        for mid, mf in universe.markets.items()
        if mf.volatility_24h is None or mf.volatility_24h <= config.max_volatility_24h
    }
    universe.markets = filtered
    return universe


def filter_by_price(
    universe: UniverseSnapshot,
    config: FilterConfig,
) -> UniverseSnapshot:
    """Remove markets with mid price below min_mid_price."""
    filtered = {
        mid: mf
        for mid, mf in universe.markets.items()
        if mf.mid_price >= config.min_mid_price
    }
    universe.markets = filtered
    return universe


def apply_all_filters(
    universe: UniverseSnapshot,
    config: FilterConfig,
) -> UniverseSnapshot:
    """Apply all standard tradability filters in sequence."""
    universe = filter_by_spread(universe, config)
    universe = filter_by_volume(universe, config)
    universe = filter_by_volatility(universe, config)
    universe = filter_by_price(universe, config)
    return universe
