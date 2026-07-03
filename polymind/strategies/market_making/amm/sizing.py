"""
AMM concentrated-liquidity position sizing.

Distributes total exposure across ladder levels, with configurable
concentration toward inner levels.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class AMMSizingConfig:
    """Configuration for AMM position sizing."""

    min_order_size: float = 1.0
    max_order_size: float = 1000.0
    total_exposure: float = 100.0  # total exposure per side
    concentration_pct: float = 0.5  # 0.0 = uniform, 1.0 = all on inner level


def distribute_size(
    total_exposure: float,
    num_levels: int,
    concentration_pct: float,
) -> list[float]:
    """Distribute total exposure across ladder levels.

    Uses linear decay from inner to outer levels. Higher concentration_pct
    skews size toward inner (level 0) levels.

    Args:
        total_exposure: Total exposure to distribute.
        num_levels: Number of levels.
        concentration_pct: 0.0 = uniform, 1.0 = all on inner level.

    Returns:
        List of sizes per level (index 0 = innermost).
    """
    if num_levels <= 0 or total_exposure <= 0:
        return [0.0] * max(num_levels, 0)

    # Compute weights with linear decay
    # concentration_pct=0 → uniform weights (all 1.0)
    # concentration_pct=1 → only first level gets weight
    if concentration_pct >= 1.0:
        weights = [1.0] + [0.0] * (num_levels - 1)
    elif concentration_pct <= 0.0:
        weights = [1.0] * num_levels
    else:
        # Linear decay: outer level gets (1 - concentration_pct) fraction of inner
        decay = 1.0 - concentration_pct
        weights = [1.0 - (i / (num_levels - 1)) * (1.0 - decay) if num_levels > 1 else 1.0
                   for i in range(num_levels)]
        weights = [max(w, 0.0) for w in weights]

    total_weight = sum(weights)
    if total_weight == 0:
        return [0.0] * num_levels

    sizes = [(w / total_weight) * total_exposure for w in weights]
    return sizes
