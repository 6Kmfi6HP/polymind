"""
AMM concentrated-liquidity ladder pricing.

Computes symmetric buy/sell price ladders around a target price, with
concentrated liquidity in a configurable spread range.
"""

from __future__ import annotations

from dataclasses import dataclass

from polymind.core.intents import OrderSide


@dataclass
class AMMPricingConfig:
    """Configuration for AMM ladder pricing."""

    min_spread: float = 0.01  # minimum spread from target (inner level)
    max_spread: float = 0.05  # maximum spread from target (outer level)
    num_levels: int = 5  # number of levels per side (buy + sell)
    tick_size: float = 0.001  # minimum price increment


def compute_ladder(
    target_price: float,
    config: AMMPricingConfig,
) -> list[tuple[OrderSide, float, int]]:
    """Compute a symmetric buy/sell ladder around a target price.

    Args:
        target_price: The reference price to center the ladder on.
        config: Pricing configuration.

    Returns:
        List of (side, price, level_index) tuples. Empty list if
        target_price is zero or negative.
    """
    if target_price <= 0:
        return []

    ladder: list[tuple[OrderSide, float, int]] = []

    for level in range(config.num_levels):
        # Linear interpolation between min and max spread
        if config.num_levels > 1:
            spread_pct = config.min_spread + (
                config.max_spread - config.min_spread
            ) * (level / (config.num_levels - 1))
        else:
            spread_pct = config.min_spread

        buy_price = target_price * (1.0 - spread_pct)
        sell_price = target_price * (1.0 + spread_pct)

        # Round to tick size
        buy_price = _round_to_tick(buy_price, config.tick_size)
        sell_price = _round_to_tick(sell_price, config.tick_size)

        ladder.append((OrderSide.BUY, buy_price, level + 1))
        ladder.append((OrderSide.SELL, sell_price, level + 1))

    return ladder


def _round_to_tick(price: float, tick_size: float) -> float:
    """Round a price to the nearest tick size."""
    if tick_size <= 0:
        return price
    return round(price / tick_size) * tick_size
