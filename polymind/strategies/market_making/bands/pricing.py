"""
Bands price-margin pricing.

Computes discrete buy/sell price bands around a target price. Each band
has its own spread percentage, enabling independent margin configuration
per band level.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import List, Tuple

from polymind.core.intents import OrderSide


@dataclass
class BandConfig:
    """Configuration for a single price band."""

    spread_pct: float  # spread from target (e.g. 0.02 = 2%)
    weight: float = 1.0  # relative size weight vs other bands


@dataclass
class BandPricingConfig:
    """Configuration for band pricing."""

    bands: List[BandConfig] = field(
        default_factory=lambda: [
            BandConfig(spread_pct=0.015),  # inner band
            BandConfig(spread_pct=0.03),  # middle band
            BandConfig(spread_pct=0.05),  # outer band
        ]
    )


def compute_band_prices(
    target_price: float,
    config: BandPricingConfig,
) -> List[Tuple[OrderSide, float, int]]:
    """Compute band prices around a target price.

    Args:
        target_price: Reference price.
        config: Band pricing configuration.

    Returns:
        List of (side, price, band_index) tuples, alternating buy/sell
        per band. Empty if target_price <= 0.
    """
    if target_price <= 0:
        return []

    result: List[Tuple[OrderSide, float, int]] = []
    for idx, band in enumerate(config.bands):
        buy_price = target_price * (1.0 - band.spread_pct)
        sell_price = target_price * (1.0 + band.spread_pct)
        result.append((OrderSide.BUY, buy_price, idx))
        result.append((OrderSide.SELL, sell_price, idx))

    return result
