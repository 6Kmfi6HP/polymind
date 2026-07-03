"""
Fair-value / microstructure factor strategy.

Scores markets based on the gap between fair value estimates and current
market price. Higher scores when market is undervalued (bid below fair value).
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

from polymind.factors.pipeline import UniverseSnapshot
from polymind.factors.registry import FactorMetadata, FactorSignalModel


@dataclass
class FairValueConfig:
    """Configuration for fair-value factor."""

    max_z_score: float = 3.0  # cap for extreme deviations


class FairValueFactor(FactorSignalModel):
    """Fair-value / microstructure factor.

    Computes a score from the distance between mid price and a
    micro-price estimate using bid/ask imbalance. Higher score when
    market is relatively undervalued.
    """

    def __init__(self, config: Optional[FairValueConfig] = None):
        self.config = config or FairValueConfig()
        metadata = FactorMetadata(
            name="fair_value",
            version="1.0.0",
            description="Fair-value / microstructure factor",
            tags=["microstructure", "fair-value"],
        )
        super().__init__(metadata)

    async def compute_scores(self, universe: UniverseSnapshot) -> Dict[str, float]:
        """Score markets by fair-value deviation.

        Micro-price = (bid_price * ask_size + ask_price * bid_size) / (bid_size + ask_size)
        Score = (micro_price - mid_price) / mid_price  (positive = undervalued)
        """
        scores: Dict[str, float] = {}
        for mid, mf in universe.markets.items():
            if mf is None or mf.mid_price <= 0:
                continue
            # Try to compute micro-price from features
            micro_price = mf.additional.get("micro_price")
            if micro_price is not None:
                deviation = (micro_price - mf.mid_price) / mf.mid_price
                deviation = max(-self.config.max_z_score, min(self.config.max_z_score, deviation))
                scores[mid] = deviation
        return scores
