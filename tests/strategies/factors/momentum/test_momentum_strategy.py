"""
Tests for Momentum factor strategy.
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from polymind.core.intents import StrategyIntent
from polymind.core.portfolio import PortfolioTarget, PositionDirection
from polymind.factors.pipeline import MarketFeatures, UniverseSnapshot
from polymind.factors.portfolio_construction import PortfolioConfig, construct_portfolio
from polymind.factors.scoring import rank_normalize
from polymind.strategies.factors.momentum.strategy import (
    MomentumBridge,
    MomentumConfig,
    MomentumFactor,
    run_momentum_pipeline,
)


def _make_universe(features: list[dict]) -> UniverseSnapshot:
    markets = {}
    for f in features:
        mid = f.pop("market_id")
        markets[mid] = MarketFeatures(market_id=mid, **f)
    return UniverseSnapshot(timestamp=datetime.now(), markets=markets)


class TestMomentumConfig:
    def test_defaults(self):
        cfg = MomentumConfig()
        assert cfg.lookback == "24h"
        assert cfg.top_n == 5
        assert cfg.long_short is True


class TestMomentumFactor:
    @pytest.mark.asyncio
    async def test_compute_scores(self):
        u = _make_universe(
            [
                {"market_id": "m1", "momentum_24h": 0.05},
                {"market_id": "m2", "momentum_24h": -0.03},
                {"market_id": "m3", "momentum_24h": 0.01},
            ]
        )
        model = MomentumFactor()
        scores = await model.compute_scores(u)
        assert scores["m1"] == 0.05
        assert scores["m2"] == -0.03
        assert scores["m3"] == 0.01

    @pytest.mark.asyncio
    async def test_lookback_7d(self):
        u = _make_universe(
            [
                {"market_id": "m1", "momentum_7d": 0.15},
            ]
        )
        cfg = MomentumConfig(lookback="7d")
        model = MomentumFactor(cfg)
        scores = await model.compute_scores(u)
        assert scores["m1"] == 0.15

    @pytest.mark.asyncio
    async def test_empty_universe(self):
        u = UniverseSnapshot(timestamp=datetime.now(), markets={})
        model = MomentumFactor()
        scores = await model.compute_scores(u)
        assert scores == {}

    def test_metadata_name(self):
        cfg = MomentumConfig(lookback="4h")
        model = MomentumFactor(cfg)
        assert model.metadata.name == "momentum_4h"
        assert "momentum" in model.metadata.tags

    @pytest.mark.asyncio
    async def test_full_pipeline_integration(self):
        """End-to-end: scores → rank → portfolio targets."""
        u = _make_universe(
            [
                {"market_id": "m1", "momentum_24h": 0.10},
                {"market_id": "m2", "momentum_24h": 0.05},
                {"market_id": "m3", "momentum_24h": -0.02},
                {"market_id": "m4", "momentum_24h": -0.08},
                {"market_id": "m5", "momentum_24h": 0.01},
            ]
        )
        model = MomentumFactor(MomentumConfig(top_n=3))
        scores = await model.compute_scores(u)
        ranked = rank_normalize(scores)

        cfg = PortfolioConfig(top_n=3)
        targets = construct_portfolio(ranked, cfg)
        assert 1 <= len(targets) <= 3

    def test_custom_config_stored(self) -> None:
        """Custom config is stored on the model instance."""
        cfg = MomentumConfig(lookback="4h", top_n=3)
        model = MomentumFactor(config=cfg)
        assert model.config is cfg
        assert model.config.lookback == "4h"
        assert model.config.top_n == 3


class TestMomentumBridge:
    """Tests for MomentumBridge."""

    def test_default_strategy_name(self) -> None:
        bridge = MomentumBridge()
        assert bridge.strategy_name == "momentum"

    def test_custom_strategy_name(self) -> None:
        bridge = MomentumBridge(strategy_name="momentum_7d")
        assert bridge.strategy_name == "momentum_7d"

    @pytest.mark.asyncio
    async def test_to_order_intents_empty(self) -> None:
        bridge = MomentumBridge()
        intents = await bridge.to_order_intents([])
        assert intents == []

    @pytest.mark.asyncio
    async def test_to_order_intents_with_targets(self) -> None:
        bridge = MomentumBridge()
        targets = [
            PortfolioTarget(
                market_id="ETH",
                direction=PositionDirection.LONG,
                target_size=42.0,
                confidence=0.85,
                rank=1,
            ),
        ]
        intents = await bridge.to_order_intents(targets)
        assert len(intents) == 1
        intent = intents[0]
        assert isinstance(intent, StrategyIntent)
        assert intent.strategy_name == "momentum"
        assert intent.metadata["market_id"] == "ETH"
        assert intent.metadata["direction"] == "LONG"
        assert intent.metadata["target_size"] == 42.0
        assert intent.metadata["confidence"] == 0.85
        assert intent.metadata["rank"] == 1


class TestRunMomentumPipeline:
    """Tests for run_momentum_pipeline convenience function."""

    @pytest.mark.filterwarnings("ignore::RuntimeWarning")
    def test_pipeline_default_config(self) -> None:
        """Default config flows through the pipeline."""
        u = _make_universe(
            [
                {"market_id": "m1", "momentum_24h": 0.05},
            ]
        )
        mock_scores = {"m1": 0.05}
        mock_ranked = {"m1": 1.0}
        mock_targets = [MagicMock(spec=PortfolioTarget)]
        mock_intents = [MagicMock(spec=StrategyIntent)]

        with (
            patch.object(MomentumFactor, "compute_scores", return_value=mock_scores),
            patch.object(MomentumBridge, "to_order_intents", return_value=mock_intents),
            patch(
                "polymind.strategies.factors.momentum.strategy.rank_normalize",
                return_value=mock_ranked,
            ),
            patch(
                "polymind.strategies.factors.momentum.strategy.construct_portfolio",
                return_value=mock_targets,
            ),
            patch("asyncio.run") as mock_run,
        ):
            mock_run.side_effect = [mock_scores, mock_intents]
            result = run_momentum_pipeline(u)

        assert result == mock_intents

    @pytest.mark.filterwarnings("ignore::RuntimeWarning")
    def test_pipeline_custom_config(self) -> None:
        """Custom config propagates through the pipeline."""
        u = _make_universe(
            [
                {"market_id": "m1", "momentum_24h": 0.05},
            ]
        )
        cfg = MomentumConfig(
            lookback="7d",
            top_n=3,
            max_exposure_per_market=50.0,
            total_exposure=200.0,
            min_confidence=0.1,
        )
        mock_scores = {"m1": 0.15}
        mock_ranked = {"m1": 1.0}
        mock_intents = [MagicMock(spec=StrategyIntent)]

        with (
            patch.object(MomentumFactor, "compute_scores", return_value=mock_scores),
            patch.object(MomentumBridge, "to_order_intents", return_value=mock_intents),
            patch(
                "polymind.strategies.factors.momentum.strategy.rank_normalize",
                return_value=mock_ranked,
            ),
            patch("polymind.strategies.factors.momentum.strategy.construct_portfolio") as mock_cp,
            patch("asyncio.run") as mock_run,
        ):
            mock_run.side_effect = [mock_scores, mock_intents]
            result = run_momentum_pipeline(u, config=cfg)

        assert result == mock_intents
        _, portfolio_cfg = mock_cp.call_args[0]
        assert portfolio_cfg.top_n == 3
        assert portfolio_cfg.max_exposure_per_market == 50.0
        assert portfolio_cfg.total_exposure == 200.0
        assert portfolio_cfg.min_confidence == 0.1
