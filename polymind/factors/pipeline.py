"""
Factor pipeline: universe → features → scores → rank → portfolio targets.

The factor pipeline is the core abstraction for cross-sectional factor
strategies. It processes market snapshots through a series of stages,
each implemented as a separate port.
"""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import datetime

from polymind.core.portfolio import PortfolioTarget


@dataclass
class UniverseSnapshot:
    """Snapshot of the entire tradable universe at a point in time."""

    timestamp: datetime
    markets: dict[str, MarketFeatures] = field(default_factory=dict)


@dataclass
class MarketFeatures:
    """Computed features for a single market."""

    market_id: str
    mid_price: float = 0.0
    spread_bps: float = 0.0
    volume_24h: float = 0.0
    momentum_4h: float | None = None
    momentum_24h: float | None = None
    momentum_7d: float | None = None
    volatility_24h: float | None = None
    additional: dict[str, float] = field(default_factory=dict)


@dataclass
class ScoreResult:
    """Result of scoring a universe."""

    scores: dict[str, float]  # market_id → score
    timestamp: datetime


class FactorPipeline:
    """Orchestrates the factor trading pipeline.

    Stages:
    1. Feature computation (universe → features)
    2. Tradability filtering (features → filtered features)
    3. Score computation (features → scores)
    4. Portfolio construction (scores → portfolio targets)
    """

    def __init__(
        self,
        feature_fn: Callable[[UniverseSnapshot], UniverseSnapshot],
        filter_fn: Callable[[UniverseSnapshot], UniverseSnapshot],
        score_fn: Callable[[UniverseSnapshot], ScoreResult],
        portfolio_fn: Callable[[ScoreResult], list[PortfolioTarget]],
    ):
        self.feature_fn = feature_fn
        self.filter_fn = filter_fn
        self.score_fn = score_fn
        self.portfolio_fn = portfolio_fn

    async def run(self, universe: UniverseSnapshot) -> list[PortfolioTarget]:
        """Run the full pipeline on a universe snapshot.

        Returns a list of PortfolioTargets for positions to take.
        """
        # Stage 1: Compute features
        featured = await self._compute_features(universe)

        # Stage 2: Apply tradability filters
        filtered = await self._apply_filters(featured)

        # Stage 3: Score
        scores = await self._compute_scores(filtered)
        if not scores.scores:
            return []

        # Stage 4: Construct portfolio
        targets = await self._construct_portfolio(scores)
        return targets

    async def _compute_features(self, universe: UniverseSnapshot) -> UniverseSnapshot:
        """Compute features for all markets in the universe."""
        return self.feature_fn(universe)

    async def _apply_filters(self, universe: UniverseSnapshot) -> UniverseSnapshot:
        """Apply tradability filters to remove untradeable markets."""
        return self.filter_fn(universe)

    async def _compute_scores(self, universe: UniverseSnapshot) -> ScoreResult:
        """Score all markets based on their features."""
        return self.score_fn(universe)

    async def _construct_portfolio(
        self, scores: ScoreResult
    ) -> list[PortfolioTarget]:
        """Convert scores into portfolio targets."""
        return self.portfolio_fn(scores)
