"""
Bands per-band position sizing.

Distributes exposure across bands, optionally weighted by each band's
weight parameter.
"""

from __future__ import annotations

from dataclasses import dataclass

from polymind.strategies.market_making.bands.pricing import BandPricingConfig


@dataclass
class BandSizingConfig:
    """Configuration for band position sizing."""

    exposure_per_band: float = 20.0  # base exposure per band (per side)


def distribute_band_sizes(
    config: BandPricingConfig,
    sizing_config: BandSizingConfig,
) -> list[float]:
    """Compute size for each band based on weight and exposure.

    Each band gets: exposure_per_band * weight.  Unless weights
    are explicitly provided, all bands get the same size.

    Args:
        config: Band pricing config (defines bands and weights).
        sizing_config: Sizing configuration.

    Returns:
        List of sizes, one per band (same order as config.bands).
    """
    return [sizing_config.exposure_per_band * band.weight for band in config.bands]
