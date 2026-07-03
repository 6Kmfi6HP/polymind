"""
Sentiment / news factor strategy.

Scores markets based on external sentiment signals. For Phase 7 MVP,
uses a placeholder that returns scores from market feature data.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from polymind.factors.pipeline import UniverseSnapshot
from polymind.factors.registry import FactorMetadata, FactorSignalModel


@dataclass
class SentimentConfig:
    """Configuration for sentiment factor."""

    source: str = "social"  # 'social', 'news', 'custom'
    decay_hours: float = 24.0  # how long a signal remains relevant


class SentimentFactor(FactorSignalModel):
    """Sentiment-based factor signal model.

    For Phase 7 MVP, uses additional feature fields. Production
    version ingests external social/news signals.
    """

    def __init__(self, config: Optional[SentimentConfig] = None):
        self.config = config or SentimentConfig()
        metadata = FactorMetadata(
            name=f"sentiment_{self.config.source}",
            version="1.0.0",
            description=f"Sentiment factor ({self.config.source} source)",
            tags=["sentiment", "social"],
        )
        super().__init__(metadata)

    async def compute_scores(self, universe: UniverseSnapshot) -> Dict[str, float]:
        """Score markets by sentiment signal.

        Falls back to 'sentiment' key in additional features.
        """
        scores: Dict[str, float] = {}
        for mid, mf in universe.markets.items():
            if mf is None:
                continue
            sentiment = mf.additional.get("sentiment")
            if sentiment is not None:
                scores[mid] = sentiment
        return scores
