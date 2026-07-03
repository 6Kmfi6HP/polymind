"""
Momentum factor strategy.

A concrete FactorSignalModel that computes momentum scores from
MarketFeatures. Supports 4h, 24h, and 7d lookback windows.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Dict, List, Optional

from polymind.core.intents import StrategyIntent
from polymind.factors.pipeline import MarketFeatures, UniverseSnapshot
from polymind.factors.portfolio_construction import PortfolioConfig, construct_portfolio
from polymind.factors.registry import FactorExecutionBridge, FactorMetadata, FactorSignalModel
from polymind.factors.scoring import momentum_score, rank_normalize


@dataclass
class MomentumConfig:
    """Configuration for momentum strategy."""

    lookback: str = "24h"  # '4h', '24h', '7d'
    top_n: int = 5
    max_exposure_per_market: float = 100.0
    total_exposure: float = 500.0
    min_confidence: float = 0.0  # no minimum for momentum (signal is relative)
    long_short: bool = True


class MomentumFactor(FactorSignalModel):
    """Momentum factor signal model.

    Scores markets by momentum: positive = upward trend,
    negative = downward trend.
    """

    def __init__(self, config: Optional[MomentumConfig] = None):
        self.config = config or MomentumConfig()
        metadata = FactorMetadata(
            name=f"momentum_{self.config.lookback}",
            version="1.0.0",
            description=f"Momentum factor ({self.config.lookback} lookback)",
            lookback=self.config.lookback,
            tags=["momentum", "trend"],
        )
        super().__init__(metadata)

    async def compute_scores(self, universe: UniverseSnapshot) -> Dict[str, float]:
        """Compute momentum scores for all markets."""
        raw_scores = momentum_score(universe, lookback=self.config.lookback)
        return raw_scores


class MomentumBridge(FactorExecutionBridge):
    """Converts momentum portfolio targets into StrategyIntents."""

    def __init__(self, strategy_name: str = "momentum"):
        self.strategy_name = strategy_name

    async def to_order_intents(
        self, targets: List
    ) -> List[StrategyIntent]:
        """Convert PortfolioTargets to StrategyIntents.

        Current implementation creates one bare StrategyIntent per target.
        Full order creation requires the execution layer.
        """
        from datetime import datetime, timezone

        from polymind.core.intents import StrategyIntent

        intents: List[StrategyIntent] = []
        for target in targets:
            intent = StrategyIntent(
                timestamp=datetime.now(timezone.utc),
                strategy_name=self.strategy_name,
                metadata={
                    "market_id": target.market_id,
                    "direction": target.direction.name,
                    "target_size": target.target_size,
                    "confidence": target.confidence,
                    "rank": target.rank,
                },
            )
            intents.append(intent)
        return intents


# Convenience: run the full momentum pipeline
def run_momentum_pipeline(
    universe: UniverseSnapshot,
    config: Optional[MomentumConfig] = None,
) -> List[StrategyIntent]:
    """Run the full momentum pipeline: score → rank → portfolio → bridge.

    Convenience function that wires together all components.
    """
    import asyncio

    cfg = config or MomentumConfig()
    model = MomentumFactor(cfg)
    bridge = MomentumBridge()

    scores = asyncio.run(model.compute_scores(universe))
    ranked = rank_normalize(scores)

    portfolio_cfg = PortfolioConfig(
        top_n=cfg.top_n,
        max_exposure_per_market=cfg.max_exposure_per_market,
        total_exposure=cfg.total_exposure,
        min_confidence=cfg.min_confidence,
    )
    targets = construct_portfolio(ranked, portfolio_cfg)
    intents = asyncio.run(bridge.to_order_intents(targets))
    return intents
