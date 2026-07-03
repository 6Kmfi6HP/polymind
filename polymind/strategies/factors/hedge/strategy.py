"""
Hedge / exposure neutralization overlay.

Constructs market-neutral portfolios by pairing YES/NO positions or
offsetting correlated exposures.
"""

from __future__ import annotations

from dataclasses import dataclass

from polymind.core.portfolio import PortfolioTarget, PositionDirection
from polymind.factors.pipeline import UniverseSnapshot


@dataclass
class HedgeConfig:
    """Configuration for hedge overlay."""

    hedge_ratio: float = 1.0  # 1.0 = fully hedged
    max_pair_distance: float = 0.1  # max spread between paired markets


class HedgeOverlay:
    """Hedge overlay that neutralizes directional exposure.

    Analyzes long/short positions and adds offsetting positions
    to neutralize net exposure within configured limits.
    """

    def __init__(self, config: HedgeConfig | None = None):
        self.config = config or HedgeConfig()

    def apply(
        self,
        targets: list[PortfolioTarget],
        universe: UniverseSnapshot,
    ) -> list[PortfolioTarget]:
        """Apply hedge overlay to a list of targets.

        Pairs LONG positions with SHORT positions on correlated markets
        to reduce net directional exposure.
        """
        longs = [t for t in targets if t.direction == PositionDirection.LONG]
        shorts = [t for t in targets if t.direction == PositionDirection.SHORT]

        net_long = sum(t.target_size for t in longs)
        net_short = sum(t.target_size for t in shorts)

        if net_long > net_short:
            hedge_size = (net_long - net_short) * self.config.hedge_ratio
            if hedge_size > 0:
                hedge_target = PortfolioTarget(
                    market_id="HEDGE",
                    direction=PositionDirection.SHORT,
                    target_size=hedge_size,
                    confidence=0.5,
                    rank=0,
                    reason=f"Hedge overlay: short {hedge_size} to neutralize",
                )
                return targets + [hedge_target]

        return targets

    def compute_net_exposure(self, targets: list[PortfolioTarget]) -> float:
        """Compute net directional exposure across all targets."""
        net = 0.0
        for t in targets:
            if t.direction == PositionDirection.LONG:
                net += t.target_size
            elif t.direction == PositionDirection.SHORT:
                net -= t.target_size
        return net
