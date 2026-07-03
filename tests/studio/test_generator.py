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
