"""
Tests for Strategy Template Library.
"""

from __future__ import annotations

from polymind.templates.base import TemplateInfo
from polymind.templates.library import TemplateLibrary


class TestTemplateInfo:
    def test_construction(self):
        info = TemplateInfo(
            name="test_template",
            description="A test template",
            strategy_type="amm",
            params={"budget": 100.0},
            risk_limits={"max_position": 50.0},
            tags=["test"],
        )
        assert info.name == "test_template"
        assert info.strategy_type == "amm"
        assert info.params["budget"] == 100.0

    def test_to_dict(self):
        info = TemplateInfo(
            name="test",
            description="desc",
            strategy_type="amm",
        )
        d = info.to_dict()
        assert d["name"] == "test"
        assert d["type"] == "amm"


class TestTemplateLibrary:
    def test_list_templates(self):
        lib = TemplateLibrary()
        templates = lib.list_templates()
        assert len(templates) >= 7
        names = [t.name for t in templates]
        assert "amm_concentrated" in names
        assert "bands_multi" in names
        assert "classic_mm_simple" in names
        assert "maker_rebate_pair" in names

    def test_get_template(self):
        lib = TemplateLibrary()
        info = lib.get_template("amm_concentrated")
        assert info is not None
        assert info.strategy_type == "amm"
        assert "budget" in info.params
        assert "max_position_size" in info.risk_limits

    def test_get_template_unknown(self):
        lib = TemplateLibrary()
        assert lib.get_template("nonexistent") is None

    def test_instantiate(self):
        lib = TemplateLibrary()
        info = lib.instantiate("amm_concentrated", overrides={"budget": 500.0})
        assert info is not None
        assert info.params["budget"] == 500.0
        # Original should be unchanged
        original = lib.get_template("amm_concentrated")
        assert original.params["budget"] == 200.0

    def test_instantiate_unknown(self):
        lib = TemplateLibrary()
        assert lib.instantiate("nope") is None

    def test_amm_template_params(self):
        lib = TemplateLibrary()
        info = lib.get_template("amm_concentrated")
        assert info.params["min_spread"] == 0.01
        assert info.params["num_levels"] == 5
        assert "market-making" in info.tags

    def test_maker_rebate_template(self):
        lib = TemplateLibrary()
        info = lib.get_template("maker_rebate_pair")
        assert info is not None
        assert info.params["merge_on_fill"] is True
        assert "arbitrage" in info.tags

    def test_momentum_template(self):
        lib = TemplateLibrary()
        info = lib.get_template("momentum_factor")
        assert info is not None
        assert info.params["lookback"] == "24h"
        assert info.params["top_n"] == 5
        assert "factor" in info.tags

    def test_sniper_template(self):
        lib = TemplateLibrary()
        info = lib.get_template("sniper_discount")
        assert info is not None
        assert info.params["discount_threshold"] == 0.50
        assert info.params["fair_value_source"] == "mid"

    def test_all_templates_have_required_fields(self):
        lib = TemplateLibrary()
        for t in lib.list_templates():
            assert t.name
            assert t.description
            assert t.strategy_type
            assert isinstance(t.params, dict)
            assert isinstance(t.risk_limits, dict)
            assert isinstance(t.tags, list)
