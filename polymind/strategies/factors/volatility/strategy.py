"""
Volatility regime factor strategy.

Scores markets by their volatility level. High volatility = high score
(for vol-targeting strategies). Configurable direction.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional

from polymind.factors.pipeline import UniverseSnapshot
from polymind.factors.registry import FactorMetadata, FactorSignalModel


@dataclass
class VolatilityConfig:
    """Configuration for volatility factor."""

    lookback: str = "24h"  # '24h', '7d'
    invert: bool = False  # True = low volatility scores higher (regime filter)


class VolatilityFactor(FactorSignalModel):
    """Volatility regime factor signal model.

    Scores markets by realized volatility. When invert=False (default),
    higher volatility = higher score (for vol-targeting).
    When invert=True, lower volatility = higher score (regime filter).
    """

    def __init__(self, config: Optional[VolatilityConfig] = None):
        self.config = config or VolatilityConfig()
        metadata = FactorMetadata(
            name=f"volatility_{self.config.lookback}",
            version="1.0.0",
            description=f"Volatility factor ({self.config.lookback} lookback)",
            lookback=self.config.lookback,
            tags=["volatility", "regime"],
        )
        super().__init__(metadata)

    async def compute_scores(self, universe: UniverseSnapshot) -> Dict[str, float]:
        """Score markets by volatility level."""
        scores: Dict[str, float] = {}
        for mid, mf in universe.markets.items():
            if mf is None:
                continue
            vol = mf.volatility_24h
            if vol is not None:
                score = -vol if self.config.invert else vol
                scores[mid] = score
        return scores
