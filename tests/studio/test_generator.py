"""
Tests for strategy generator (NL → typed config).
"""

from __future__ import annotations

from polymind.studio.generator import (
    GeneratedConfig,
    GenerationError,
    StrategyGenerator,
    StrategyTemplate,
)


class TestStrategyTemplate:
    def test_mm_template(self):
        tpl = StrategyTemplate.AMM
        assert tpl.name == "AMM"
        assert "min_spread" in tpl.required_params
        assert "num_levels" in tpl.defaults

    def test_bands_template(self):
        tpl = StrategyTemplate.BANDS
        assert tpl.name == "BANDS"
        assert len(tpl.required_params) > 0

    def test_momentum_template(self):
        tpl = StrategyTemplate.MOMENTUM
        assert tpl.name == "MOMENTUM"
        assert tpl.defaults["lookback"] == "24h"


class TestStrategyGenerator:
    def test_amm_description(self):
        gen = StrategyGenerator()
        result = gen.generate("Run AMM market making on BTC with 5 levels, min spread 1%")
        assert isinstance(result, GeneratedConfig)
        assert result.template == StrategyTemplate.AMM
        assert result.confidence > 0

    def test_bands_description(self):
        gen = StrategyGenerator()
        result = gen.generate("Use bands strategy with margin bands at 2% and 5%")
        assert result.template == StrategyTemplate.BANDS

    def test_factor_momentum(self):
        gen = StrategyGenerator()
        result = gen.generate("Run cross-sectional momentum factor with 7d lookback, top 10")
        assert result.template == StrategyTemplate.MOMENTUM

    def test_unknown_strategy(self):
        gen = StrategyGenerator()
        result = gen.generate("Do something completely different")
        assert result.template == StrategyTemplate.CUSTOM
        assert result.confidence < 0.5

    def test_extract_params(self):
        gen = StrategyGenerator()
        result = gen.generate("AMM with 10 levels and 2% spread")
        params = result.params
        assert "num_levels" in params
        assert params["num_levels"] == 10

    def test_params_validated(self):
        gen = StrategyGenerator()
        result = gen.generate("AMM with 0 levels")
        # Should still work but clamp
        assert result.params.get("num_levels", 0) > 0

    def test_full_config_output(self):
        gen = StrategyGenerator()
        result = gen.generate("Bands at 1%, 3%, 5% spreads, size 50")
        assert result.strategy_name
        assert result.confidence > 0
        assert result.validated is True

    # ── New tests for missing coverage branches ────────────────────────

    def test_maker_rebate_match(self):
        """Cover _match_maker_rebate path."""
        gen = StrategyGenerator()
        result = gen.generate("maker rebate on ETH")
        assert result.template == StrategyTemplate.CUSTOM
        assert result.strategy_name == "maker_rebate"
        assert result.confidence == 0.8

    def test_classic_mm_match(self):
        """Cover _match_classic_mm path."""
        gen = StrategyGenerator()
        result = gen.generate("classic MM on BTC with 1.5% spread")
        assert result.template == StrategyTemplate.CLASSIC_MM
        assert result.params.get("spread_pct") == 0.015

    def test_momentum_4h_lookback(self):
        """Cover 4h lookback branch in _match_momentum."""
        gen = StrategyGenerator()
        result = gen.generate("momentum with 4 hour lookback top 3")
        assert result.params.get("lookback") == "4h"
        assert result.params.get("top_n") == 3

    def test_momentum_24h_lookback(self):
        """Default lookback is 24h when no explicit period is given."""
        gen = StrategyGenerator()
        # 24h/24hour contains 4h/4hour as substring, so the 24h branch
        # in _match_momentum is only reachable as the default fallback
        result = gen.generate("momentum daily lookback top 3")
        assert result.params.get("lookback") == "24h"

    def test_momentum_no_top_n_defaults(self):
        """_extract_int returns default when regex doesn't match."""
        gen = StrategyGenerator()
        result = gen.generate("momentum with daily lookback")
        assert result.params.get("top_n") == 5  # default
        assert result.params.get("lookback") == "24h"  # default

    def test_factor_discovery_routing(self):
        """_match_factor_discovery returns FACTOR template."""
        gen = StrategyGenerator()
        # Use "discover" keyword (confidence 0.75) without "factor" (0.9)
        result = gen.generate("discover volatility signal 30d lookback top 5")
        assert result.template == StrategyTemplate.FACTOR

    def test_factor_discovery_exception_fallback(self):
        """_match_factor_discovery except handler (lines 126-128) falls back to momentum."""
        from unittest.mock import patch

        gen = StrategyGenerator()
        with patch("polymind.studio.factor_discovery.FactorDiscoveryAgent") as mock_agent_cls:
            mock_agent = mock_agent_cls.return_value
            mock_agent.discover.side_effect = RuntimeError("discovery failed")
            result = gen.generate("discover factor momentum 7d")
            assert result.template == StrategyTemplate.MOMENTUM

    def test_bands_no_pct_defaults(self):
        """Bands without percentage values uses default spreads."""
        gen = StrategyGenerator()
        result = gen.generate("bands strategy")
        assert result.template == StrategyTemplate.BANDS
        assert result.params["band_spreads"] == [0.015, 0.03, 0.05]

    def test_bands_multiple_pcts(self):
        """Extract multiple % values for band_spreads."""
        gen = StrategyGenerator()
        result = gen.generate("bands at 1%, 3%, 5% spreads")
        assert result.template == StrategyTemplate.BANDS
        assert result.params["band_spreads"] == [0.01, 0.03, 0.05]

    def test_amm_max_spread_scaling(self):
        """max_spread = min_spread * 5 in AMM."""
        gen = StrategyGenerator()
        result = gen.generate("AMM with 3 levels, 2.5% spread")
        assert result.params["num_levels"] == 3
        assert result.params["min_spread"] == 0.025
        assert result.params["max_spread"] == 0.125


class TestGeneratedConfig:
    def test_minimal(self):
        cfg = GeneratedConfig(
            template=StrategyTemplate.AMM,
            strategy_name="test",
            params={"num_levels": 5},
            confidence=0.8,
        )
        assert cfg.template == StrategyTemplate.AMM
        assert cfg.validated is True

    def test_to_summary(self):
        cfg = GeneratedConfig(
            template=StrategyTemplate.AMM,
            strategy_name="amm_btc",
            params={"num_levels": 5, "min_spread": 0.01},
            confidence=0.9,
        )
        summary = cfg.to_summary()
        assert "amm_btc" in summary
        assert "AMM" in summary


class TestGenerationError:
    def test_error(self):
        err = GenerationError("no template matched")
        assert str(err) == "no template matched"
