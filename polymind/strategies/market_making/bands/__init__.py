"""
Bands price-margin market-making strategy.

Port of the official Polymarket keeper's Bands strategy, adapted for the
intent-executor architecture (ADR 0002).
"""

from __future__ import annotations

from polymind.strategies.market_making.bands.pricing import (
    BandConfig,
    BandPricingConfig,
    compute_band_prices,
)
from polymind.strategies.market_making.bands.sizing import BandSizingConfig, distribute_band_sizes
from polymind.strategies.market_making.bands.strategy import BandsStrategy

__all__ = [
    "BandConfig",
    "BandPricingConfig",
    "BandSizingConfig",
    "BandsStrategy",
    "compute_band_prices",
    "distribute_band_sizes",
]
