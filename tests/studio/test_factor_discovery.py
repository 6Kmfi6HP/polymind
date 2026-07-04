"""
Tests for AI Factor Discovery Engine.
"""

from __future__ import annotations

import pytest

from polymind.studio.factor_discovery import (
    FACTOR_APPROVAL_MAX_DRAWDOWN,
    FACTOR_APPROVAL_MIN_SHARPE,
    FactorCard,
    FactorDefinition,
    FactorDiscoveryAgent,
)


class TestFactorDefinition:
    def test_construction(self):
        fd = FactorDefinition(
            name="test_factor",
            description="7d momentum, top quintile",
            lookback="7d",
            scoring_fn="momentum",
            top_n=5,
            rebal_freq_hours=4,
        )
        assert fd.name == "test_factor"
        assert fd.lookback == "7d"
        assert fd.top_n == 5

    def test_defaults(self):
        fd = FactorDefinition()
        assert fd.lookback == "24h"
        assert fd.top_n == 5
        assert fd.scoring_fn == "momentum"


class TestFactorCard:
    def test_construction(self):
        fd = FactorDefinition(name="fact")
        card = FactorCard(
            definition=fd,
            sharpe=1.5,
            total_return=0.25,
            approved=True,
        )
        assert card.approved is True
        assert "APPROVED" in card.summary

    def test_rejected_card(self):
        fd = FactorDefinition(name="bad")
        card = FactorCard(definition=fd, sharpe=-0.5, approved=False)
        assert card.approved is False
        assert "REJECTED" in card.summary

    def test_summary_format(self):
        fd = FactorDefinition(name="momentum_7d")
        card = FactorCard(
            definition=fd,
            sharpe=1.2,
            total_return=0.15,
            max_drawdown=0.3,
            total_trades=50,
            approved=True,
        )
        summary = card.summary
        assert "momentum_7d" in summary
        assert "Sharpe=1.20" in summary

    def test_empty_error(self):
        fd = FactorDefinition()
        card = FactorCard(definition=fd)
        assert card.error == ""


class TestFactorDiscoveryAgent:
    @pytest.mark.asyncio
    async def test_discover_momentum(self):
        agent = FactorDiscoveryAgent()
        fd = await agent.discover("cross-sectional momentum on 7d returns, top decile, 4h hold")

        assert fd.lookback == "7d"
        assert fd.top_n == 10  # decile
        assert fd.rebal_freq_hours == 4
        assert "momentum" in fd.scoring_fn

    @pytest.mark.asyncio
    async def test_discover_volatility(self):
        agent = FactorDiscoveryAgent()
        fd = await agent.discover("volatility regime detection, 30d lookback, top 3")
        assert fd.lookback == "30d"
        assert fd.scoring_fn == "volatility"
        assert fd.top_n == 3

    @pytest.mark.asyncio
    async def test_discover_sentiment(self):
        agent = FactorDiscoveryAgent()
        fd = await agent.discover("sentiment analysis on 24h news, quintile")
        assert fd.scoring_fn == "sentiment"
        assert fd.top_n == 5

    @pytest.mark.asyncio
    async def test_discover_fair_value(self):
        agent = FactorDiscoveryAgent()
        fd = await agent.discover("fair value micro-structure signal, 14d")
        assert fd.scoring_fn == "fair_value"
        assert fd.lookback == "14d"

    @pytest.mark.asyncio
    async def test_discover_custom_params(self):
        agent = FactorDiscoveryAgent()
        fd = await agent.discover("short-term reversal, 4h lookback, top 20")
        assert fd.params.get("direction") == "short"
        assert fd.lookback == "4h"
        assert fd.top_n == 20

    @pytest.mark.asyncio
    async def test_discover_name_inference(self):
        agent = FactorDiscoveryAgent()
        fd = await agent.discover("momentum using 7d returns")
        assert fd.name == "momentum_returns"

    @pytest.mark.asyncio
    async def test_backtest_mock_data(self):
        agent = FactorDiscoveryAgent()
        fd = FactorDefinition(name="test", lookback="7d", top_n=3)
        card = await agent.backtest(fd)
        assert card.definition.name == "test"
        assert card.total_trades >= 0
        assert isinstance(card.approved, bool)

    @pytest.mark.asyncio
    async def test_backtest_empty_definition(self):
        agent = FactorDiscoveryAgent()
        fd = FactorDefinition()
        card = await agent.backtest(fd)
        # Should still produce a result (with mock data)
        assert isinstance(card, FactorCard)

    @pytest.mark.asyncio
    async def test_discover_and_backtest_pipeline(self):
        agent = FactorDiscoveryAgent()
        card = await agent.discover_and_backtest("momentum 7d top decile")
        assert isinstance(card, FactorCard)
        assert isinstance(card.definition, FactorDefinition)
        assert card.definition.lookback == "7d"
        assert card.definition.top_n == 10

    @pytest.mark.asyncio
    async def test_approval_thresholds(self):
        """Verify approval threshold constants are reasonable."""
        assert FACTOR_APPROVAL_MIN_SHARPE > 0
        assert FACTOR_APPROVAL_MAX_DRAWDOWN > 0 and FACTOR_APPROVAL_MAX_DRAWDOWN < 1
