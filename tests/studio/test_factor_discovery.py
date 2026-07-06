"""
Tests for AI Factor Discovery Engine.
"""

from __future__ import annotations

import pytest

from polymind.backtesting.factor_bt import ExecutionEvidence
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
        assert hasattr(card, "execution_evidence")
        assert card.execution_evidence.execution_model == "paper"

    def test_rejected_card(self):
        fd = FactorDefinition(name="bad")
        card = FactorCard(definition=fd, sharpe=-0.5, approved=False)
        assert card.approved is False
        assert "REJECTED" in card.summary
        assert card.execution_evidence.live_result is False

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

    def test_execution_evidence_defaults(self):
        """FactorCard execution_evidence defaults to paper assumptions."""
        fd = FactorDefinition(name="test")
        card = FactorCard(definition=fd)
        ev = card.execution_evidence
        assert ev.execution_model == "paper"
        assert ev.slippage_model == "zero-cost"
        assert ev.fill_rate == 1.0
        assert ev.avg_slippage_bps == 0.0

    def test_execution_evidence_custom(self):
        """ExecutionEvidence can be set to live mode."""
        from polymind.backtesting.factor_bt import ExecutionEvidence

        fd = FactorDefinition(name="live_test")
        ev = ExecutionEvidence(
            execution_model="live",
            slippage_model="fixed 3bps",
            fill_rate=0.95,
            avg_slippage_bps=3.5,
            total_execution_cost_bps=7.2,
            live_result=True,
        )
        card = FactorCard(definition=fd, execution_evidence=ev)
        assert "Exec: live" in card.summary
        assert card.execution_evidence.avg_slippage_bps == 3.5


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
        assert isinstance(card.execution_evidence, ExecutionEvidence)
        assert card.execution_evidence.execution_model == "paper"

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

    # ── LLM branch coverage (no API keys → fallback to keyword) ────────

    @pytest.mark.asyncio
    async def test_discover_with_llm_no_keys(self):
        """When use_llm=True but no API keys set, falls back to keyword parsing."""
        agent = FactorDiscoveryAgent()
        fd = await agent.discover("momentum 7d top decile", use_llm=True)
        assert fd.lookback == "7d"
        assert fd.top_n == 10

    @pytest.mark.asyncio
    async def test_discover_with_llm_anthropic_key_no_openai(self):
        """Anthropic key set → _discover_with_anthropic runs (fails → fallback)."""
        agent = FactorDiscoveryAgent(anthropic_api_key="sk-ant-test")
        fd = await agent.discover("sentiment 30d top quintile", use_llm=True)
        assert fd.scoring_fn == "sentiment"
        assert fd.lookback == "30d"
        assert fd.top_n == 5

    @pytest.mark.asyncio
    async def test_discover_with_llm_openai_key_only(self):
        """OpenAI key set → _discover_with_openai runs (fails → fallback)."""
        agent = FactorDiscoveryAgent(openai_api_key="sk-openai-test")
        fd = await agent.discover("volatility 14d top 3", use_llm=True)
        assert fd.scoring_fn == "volatility"
        assert fd.lookback == "14d"
        assert fd.top_n == 3

    def test_factor_card_summary_includes_name(self):
        """Summary includes the factor name (error field tested elsewhere)."""
        fd = FactorDefinition(name="my_factor")
        card = FactorCard(definition=fd, error="")
        assert "my_factor" in card.summary

    def test_factor_definition_fields(self):
        """Verify all FactorDefinition fields are accessible."""
        fd = FactorDefinition(
            name="test_factor",
            description="my factor",
            lookback="7d",
            scoring_fn="momentum",
            top_n=5,
            rebal_freq_hours=4,
            params={"direction": "long"},
        )
        assert fd.name == "test_factor"
        assert fd.lookback == "7d"
        assert fd.scoring_fn == "momentum"
        assert fd.top_n == 5

    @pytest.mark.asyncio
    async def test_infer_lookback_default(self):
        """_infer_lookback returns 24h when no pattern matches (line 329)."""
        assert FactorDiscoveryAgent._infer_lookback("no pattern here") == "24h"

    @pytest.mark.asyncio
    async def test_discover_volatility_30d(self):
        """Volatility detection with 30d (supported lookback)."""
        agent = FactorDiscoveryAgent()
        fd = await agent.discover("rolling window volatility 30d, top 10")
        assert fd.scoring_fn == "volatility"
        assert fd.lookback == "30d"
        assert fd.top_n == 10

    # ── LLM mock tests (cover _discover_with_anthropic / _discover_with_openai) ─

    @pytest.mark.asyncio
    async def test_discover_with_anthropic_success(self):
        """Mock Anthropic API via module-level import in factor_discovery."""
        from unittest.mock import AsyncMock, MagicMock, patch

        agent = FactorDiscoveryAgent(anthropic_api_key="sk-ant-real")
        fd_fallback = FactorDefinition(
            name="fallback",
            lookback="24h",
            scoring_fn="momentum",
            top_n=5,
        )

        mock_content = MagicMock()
        mock_content.text = '{"name":"ai_factor","lookback":"7d","scoring_fn":"volatility","top_n":10,"rebal_freq_hours":6}'
        mock_response = MagicMock()
        mock_response.content = [mock_content]

        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(return_value=mock_response)
        mock_module = MagicMock()
        mock_module.AsyncAnthropic.return_value = mock_client

        with patch.dict("sys.modules", {"anthropic": mock_module}):
            # Clear module-level import cache
            import polymind.studio.factor_discovery as fd_mod

            # Force re-import by deleting the cached import
            fd_mod.anthropic = mock_module  # type: ignore[attr-defined]
            result = await agent._discover_with_anthropic("test description", fd_fallback)
            assert result.name == "ai_factor"
            assert result.lookback == "7d"
            assert result.top_n == 10

    @pytest.mark.asyncio
    async def test_discover_with_anthropic_failure(self):
        """Anthropic API raises → returns fallback."""
        from unittest.mock import AsyncMock, MagicMock, patch

        agent = FactorDiscoveryAgent(anthropic_api_key="sk-ant-real")
        fd_fallback = FactorDefinition(name="fb", lookback="24h", scoring_fn="momentum", top_n=5)

        mock_client = AsyncMock()
        mock_client.messages.create = AsyncMock(side_effect=ValueError("API error"))
        mock_module = MagicMock()
        mock_module.AsyncAnthropic.return_value = mock_client

        with patch.dict("sys.modules", {"anthropic": mock_module}):
            import polymind.studio.factor_discovery as fd_mod

            fd_mod.anthropic = mock_module  # type: ignore[attr-defined]
            result = await agent._discover_with_anthropic("test", fd_fallback)
            assert result is fd_fallback

    @pytest.mark.asyncio
    async def test_discover_with_openai_success(self):
        """Mock OpenAI API via module-level import in factor_discovery."""
        from unittest.mock import AsyncMock, MagicMock, patch

        agent = FactorDiscoveryAgent(openai_api_key="sk-openai-real")
        fd_fallback = FactorDefinition(
            name="fb",
            lookback="24h",
            scoring_fn="momentum",
            top_n=5,
        )

        mock_choice = MagicMock()
        mock_choice.message.content = '{"name":"gpt_factor","lookback":"14d","scoring_fn":"sentiment","top_n":3,"rebal_freq_hours":8}'
        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
        mock_module = MagicMock()
        mock_module.AsyncOpenAI.return_value = mock_client

        with patch.dict("sys.modules", {"openai": mock_module}):
            import polymind.studio.factor_discovery as fd_mod

            fd_mod.openai = mock_module  # type: ignore[attr-defined]
            result = await agent._discover_with_openai("test", fd_fallback)
            assert result.name == "gpt_factor"
            assert result.lookback == "14d"
            assert result.top_n == 3

    @pytest.mark.asyncio
    async def test_discover_with_openai_failure(self):
        """OpenAI API raises → returns fallback."""
        from unittest.mock import AsyncMock, MagicMock, patch

        agent = FactorDiscoveryAgent(openai_api_key="sk-openai-real")
        fd_fallback = FactorDefinition(name="fb", lookback="24h", scoring_fn="momentum", top_n=5)

        mock_client = AsyncMock()
        mock_client.chat.completions.create = AsyncMock(side_effect=RuntimeError("OpenAI down"))
        mock_module = MagicMock()
        mock_module.AsyncOpenAI.return_value = mock_client

        with patch.dict("sys.modules", {"openai": mock_module}):
            import polymind.studio.factor_discovery as fd_mod

            fd_mod.openai = mock_module  # type: ignore[attr-defined]
            result = await agent._discover_with_openai("test", fd_fallback)
            assert result is fd_fallback

    # ── Static helper coverage ───────────────────────────────────────────

    def test_mock_scores(self):
        scores = FactorDiscoveryAgent._mock_scores()
        assert isinstance(scores, dict)
        assert len(scores) == 10

    def test_mock_snapshots(self):
        snaps = FactorDiscoveryAgent._mock_snapshots()
        assert isinstance(snaps, dict)
        assert len(snaps) == 10

    def test_parse_lookback_days(self):
        assert FactorDiscoveryAgent._parse_lookback_days("7d") == 7
        assert FactorDiscoveryAgent._parse_lookback_days("4h") == 1
        assert FactorDiscoveryAgent._parse_lookback_days("24h") == 1
        assert FactorDiscoveryAgent._parse_lookback_days("x") == 1

    def test_infer_rebal_freq(self):
        assert FactorDiscoveryAgent._infer_rebal_freq("every 6 hours") == 6
        assert FactorDiscoveryAgent._infer_rebal_freq("2 days") == 48
        assert FactorDiscoveryAgent._infer_rebal_freq("no number here") == 4  # default

    def test_infer_params_long(self):
        params = FactorDiscoveryAgent._infer_params("long bias bullish signal")
        assert params.get("direction") == "long"

    def test_infer_params_none(self):
        params = FactorDiscoveryAgent._infer_params("neutral signal")
        assert params == {}

    def test_infer_name_fallback(self):
        name = FactorDiscoveryAgent._infer_name("a an the on in of for to with and or is are")
        assert name == "custom_factor"

    def test_infer_name_with_filler(self):
        name = FactorDiscoveryAgent._infer_name("the momentum using daily returns")
        assert name is not None

    def test_factor_discovery_error(self):
        from polymind.studio.factor_discovery import FactorDiscoveryError

        err = FactorDiscoveryError("test error")
        assert str(err) == "test error"

    # ── backtest edge cases ──────────────────────────────────────────────

    @pytest.mark.asyncio
    async def test_backtest_custom_data(self):
        """backtest with custom snapshots and scores."""
        from datetime import datetime

        from polymind.execution.fill_model import MarketSnapshot

        agent = FactorDiscoveryAgent()
        fd = FactorDefinition(name="test", lookback="7d", top_n=2)
        snapshots = {
            "mkt1": [
                MarketSnapshot(
                    market_id="mkt1",
                    timestamp=datetime(2026, 7, 4),
                    bid_price=0.45,
                    ask_price=0.55,
                    mid_price=0.50,
                    bid_size=1000,
                    ask_size=1000,
                ),
            ],
            "mkt2": [
                MarketSnapshot(
                    market_id="mkt2",
                    timestamp=datetime(2026, 7, 4),
                    bid_price=0.40,
                    ask_price=0.50,
                    mid_price=0.45,
                    bid_size=1000,
                    ask_size=1000,
                ),
            ],
        }
        scores = {"mkt1": 1.0, "mkt2": 0.5}
        card = await agent.backtest(fd, snapshots=snapshots, scores=scores)
        assert isinstance(card, FactorCard)

    @pytest.mark.asyncio
    async def test_backtest_exception(self):
        """backtest triggers exception handler line 258-259."""
        from unittest.mock import patch

        agent = FactorDiscoveryAgent()
        fd = FactorDefinition(name="bad", lookback="7d", top_n=1)
        with patch("polymind.studio.factor_discovery.FactorBacktester") as mock_bt_cls:
            mock_bt = mock_bt_cls.return_value
            mock_bt.run.side_effect = ValueError("backtest crashed")
            card = await agent.backtest(fd)
            assert isinstance(card, FactorCard)
            assert card.error != ""

    @pytest.mark.asyncio
    async def test_discover_and_backtest_custom(self):
        """discover_and_backtest with custom data."""
        from datetime import datetime

        from polymind.execution.fill_model import MarketSnapshot

        agent = FactorDiscoveryAgent()
        snapshots = {
            "mkt1": [
                MarketSnapshot(
                    market_id="mkt1",
                    timestamp=datetime(2026, 7, 4),
                    bid_price=0.45,
                    ask_price=0.55,
                    mid_price=0.50,
                    bid_size=1000,
                    ask_size=1000,
                ),
            ],
        }
        scores = {"mkt1": 0.8}
        card = await agent.discover_and_backtest(
            "momentum 7d top quintile", snapshots=snapshots, scores=scores
        )
        assert isinstance(card, FactorCard)

    # ── Advanced analytics integration tests ────────────────────────────────

    def test_factor_card_summary_includes_ic(self):
        """Summary includes IC and WF metrics when available."""
        fd = FactorDefinition(name="ic_factor", lookback="7d", top_n=5)
        card = FactorCard(
            definition=fd,
            sharpe=1.2,
            ic_rank=0.45,
            ic_hit_rate=0.75,
            wf_sharpe_mean=0.80,
            wf_sharpe_std=0.30,
        )
        summary = card.summary
        assert "IC=0.45" in summary
        assert "WF_Sharpe=0.80" in summary

    def test_factor_card_summary_no_ic(self):
        """Summary without IC uses basic fields."""
        fd = FactorDefinition(name="plain")
        card = FactorCard(definition=fd, sharpe=0.5)
        assert "IC=" not in card.summary
        assert "WF_Sharpe" not in card.summary

    def test_factor_card_new_fields_default(self):
        """All new advanced fields default to 0.0."""
        fd = FactorDefinition(name="test")
        card = FactorCard(definition=fd)
        assert card.ic_rank == 0.0
        assert card.ic_ir == 0.0
        assert card.ic_hit_rate == 0.0
        assert card.ic_decile_1 == 0.0
        assert card.ic_decile_10 == 0.0
        assert card.decay_half_life == 0.0
        assert card.wf_sharpe_mean == 0.0
        assert card.wf_sharpe_std == 0.0
        assert card.wf_sharpe_consistency == 0.0
        assert card.wf_avg_drawdown == 0.0
        assert card.execution_evidence.execution_model == "paper"

    @pytest.mark.asyncio
    async def test_backtest_populates_ic_rank(self):
        """backtest with custom data should populate IC metrics."""
        from datetime import datetime

        from polymind.execution.fill_model import MarketSnapshot

        agent = FactorDiscoveryAgent()
        fd = FactorDefinition(name="momentum_bt", lookback="7d", top_n=3)

        # Create 15 markets where scores and mid prices are positively correlated
        snapshots: dict[str, list[MarketSnapshot]] = {}
        scores: dict[str, float] = {}
        for i in range(15):
            mid = 0.30 + i * 0.03  # ascending mid prices
            mkt_id = f"mkt{i}"
            snapshots[mkt_id] = [
                MarketSnapshot(
                    market_id=mkt_id,
                    timestamp=datetime(2026, 7, 4),
                    bid_price=mid - 0.02,
                    ask_price=mid + 0.02,
                    mid_price=mid,
                    bid_size=1000,
                    ask_size=1000,
                ),
            ]
            scores[mkt_id] = i * 0.05 + 0.10  # ascending scores (positive correlation)

        card = await agent.backtest(fd, snapshots=snapshots, scores=scores)
        # IC should be non-zero positive (scores and returns are correlated)
        assert card.ic_rank > 0
        assert card.ic_hit_rate > 0

    @pytest.mark.asyncio
    async def test_backtest_advanced_analytics_few_markets(self):
        """With only 2 markets, IC analysis returns defaults."""
        from datetime import datetime

        from polymind.execution.fill_model import MarketSnapshot

        agent = FactorDiscoveryAgent()
        fd = FactorDefinition(name="tiny", lookback="7d", top_n=1)

        snapshots = {
            "m1": [
                MarketSnapshot(
                    market_id="m1",
                    timestamp=datetime(2026, 7, 4),
                    bid_price=0.45,
                    ask_price=0.55,
                    mid_price=0.50,
                    bid_size=100,
                    ask_size=100,
                ),
            ],
            "m2": [
                MarketSnapshot(
                    market_id="m2",
                    timestamp=datetime(2026, 7, 4),
                    bid_price=0.35,
                    ask_price=0.45,
                    mid_price=0.40,
                    bid_size=100,
                    ask_size=100,
                ),
            ],
        }
        scores = {"m1": 0.9, "m2": 0.1}
        card = await agent.backtest(fd, snapshots=snapshots, scores=scores)
        # Fewer than 3 overlapping markets -> IC defaults to 0
        assert card.ic_rank == 0.0

    def test_compute_advanced_analytics(self):
        """_compute_advanced_analytics returns expected keys."""
        from datetime import datetime

        from polymind.execution.fill_model import MarketSnapshot
        from polymind.studio.factor_discovery import FactorDiscoveryAgent

        agent = FactorDiscoveryAgent()
        # Scores and forward returns (ask - mid) should vary to get meaningful IC
        scores = {f"m{i}": i * 0.06 + 0.10 for i in range(15)}  # ascending scores
        snapshots = {
            f"m{i}": MarketSnapshot(
                market_id=f"m{i}",
                timestamp=datetime(2026, 7, 4),
                bid_price=0.40 + i * 0.02,
                ask_price=0.50 + i * 0.03,  # non-constant spread
                mid_price=0.45 + i * 0.02,
                bid_size=1000,
                ask_size=1000,
            )
            for i in range(15)
        }

        result = agent._compute_advanced_analytics(scores, snapshots)
        assert "ic_rank" in result
        assert "ic_hit_rate" in result
        assert "decay_half_life" in result
        assert result["ic_rank"] != 0.0  # Correlation should exist

    def test_compute_advanced_analytics_empty(self):
        """With empty data, all analytics return 0."""
        from polymind.studio.factor_discovery import FactorDiscoveryAgent

        agent = FactorDiscoveryAgent()
        result = agent._compute_advanced_analytics({}, {})
        assert result["ic_rank"] == 0.0
        assert result["wf_sharpe_mean"] == 0.0
