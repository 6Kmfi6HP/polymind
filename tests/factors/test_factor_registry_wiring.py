"""Tests for PluginRegistry wiring in FactorRegistry."""

from __future__ import annotations

import pytest

from polymind.core.plugin import PluginRegistry
from polymind.factors.pipeline import UniverseSnapshot
from polymind.factors.registry import (
    FactorMetadata,
    FactorRegistry,
    FactorSignalModel,
    register_builtin_factors,
)


class _TestSignal(FactorSignalModel):
    """Minimal test signal for wiring tests."""

    async def compute_scores(self, universe: UniverseSnapshot) -> dict[str, float]:
        return {}


class _OtherSignal(FactorSignalModel):
    """Another test signal."""

    async def compute_scores(self, universe: UniverseSnapshot) -> dict[str, float]:
        return {}


@pytest.fixture(autouse=True)
def _reset_plugin_registry() -> None:
    """Reset PluginRegistry before each test for isolation."""
    PluginRegistry.reset()


class TestFactorRegistryWiring:
    """FactorRegistry <-> PluginRegistry integration tests."""

    # ----------------------------------------------------------------
    # register_signal also registers with PluginRegistry
    # ----------------------------------------------------------------

    def test_register_signal_registers_with_plugin_registry(self) -> None:
        reg = FactorRegistry()
        model = _TestSignal(FactorMetadata(name="test"))
        reg.register_signal("my_factor", model)

        # Should be in FactorRegistry
        assert reg.get_signal("my_factor") is model

        # Should also be in PluginRegistry
        cls = PluginRegistry().get_factor("my_factor")
        assert cls is _TestSignal

    def test_register_signal_stores_class_not_instance(self) -> None:
        reg = FactorRegistry()
        model = _TestSignal(FactorMetadata(name="test"))
        reg.register_signal("my_factor", model)

        cls = PluginRegistry().get_factor("my_factor")
        assert cls is model.__class__
        # PluginRegistry stores types, not instances
        assert cls is _TestSignal

    # ----------------------------------------------------------------
    # list_signals merges built-in and PluginRegistry
    # ----------------------------------------------------------------

    def test_list_signals_returns_builtin(self) -> None:
        reg = FactorRegistry()
        reg.register_signal("a", _TestSignal(FactorMetadata(name="a")))
        reg.register_signal("b", _TestSignal(FactorMetadata(name="b")))
        signals = reg.list_signals()
        assert "a" in signals
        assert "b" in signals

    def test_list_signals_includes_plugin_registry_entries(self) -> None:
        # Register directly into PluginRegistry (not via FactorRegistry)
        PluginRegistry().register_factor("plugin_only", _TestSignal)

        reg = FactorRegistry()
        # Register one built-in
        model = _TestSignal(FactorMetadata(name="builtin"))
        reg.register_signal("builtin", model)

        signals = reg.list_signals()
        assert "builtin" in signals
        assert "plugin_only" in signals

    def test_list_signals_deduplicates(self) -> None:
        reg = FactorRegistry()
        model = _TestSignal(FactorMetadata(name="dup"))
        reg.register_signal("dup", model)

        # Same name via PluginRegistry (e.g. from another registration path)
        PluginRegistry().register_factor("other", _OtherSignal)

        signals = reg.list_signals()
        # "dup" should appear exactly once
        assert signals.count("dup") == 1

    # ----------------------------------------------------------------
    # get_signal falls back to PluginRegistry
    # ----------------------------------------------------------------

    def test_get_signal_returns_builtin_first(self) -> None:
        reg = FactorRegistry()

        # Register a signal via FactorRegistry
        builtin_model = _TestSignal(FactorMetadata(name="builtin"))
        reg.register_signal("builtin", builtin_model)

        # Register a different name via PluginRegistry
        PluginRegistry().register_factor("plugin_only", _OtherSignal)

        # Builtin signal returns the exact instance
        assert reg.get_signal("builtin") is builtin_model

        # Plugin-only signal is resolved via fallback
        plugin_signal = reg.get_signal("plugin_only")
        assert plugin_signal is not None
        assert isinstance(plugin_signal, _OtherSignal)

    def test_get_signal_falls_back_to_plugin_registry(self) -> None:
        PluginRegistry().register_factor("lazy", _TestSignal)

        reg = FactorRegistry()
        signal = reg.get_signal("lazy")
        assert signal is not None
        assert isinstance(signal, _TestSignal)
        assert signal.metadata.name == "lazy"

    def test_get_signal_returns_none_when_not_found(self) -> None:
        reg = FactorRegistry()
        assert reg.get_signal("nonexistent") is None

    # ----------------------------------------------------------------
    # register_builtin_factors
    # ----------------------------------------------------------------

    def test_register_builtin_factors_registers_known_factors(self) -> None:
        register_builtin_factors()

        factors = PluginRegistry().list_factors()
        assert "momentum" in factors
        assert "volatility" in factors
        assert "sentiment" in factors
        assert "fair_value" in factors

    def test_register_builtin_factors_classes_are_factor_signal_models(self) -> None:
        register_builtin_factors()

        for name, cls in PluginRegistry().list_factors().items():
            assert issubclass(cls, FactorSignalModel), f"{name} is not a FactorSignalModel"

    def test_register_builtin_factors_can_be_discovered(self) -> None:
        register_builtin_factors()

        reg = FactorRegistry()
        for name in ("momentum", "volatility", "sentiment", "fair_value"):
            # These should appear in list_signals even though they were
            # registered via PluginRegistry, not FactorRegistry.
            assert name in reg.list_signals()

    # ----------------------------------------------------------------
    # Duplicate via PluginRegistry raises ValueError
    # ----------------------------------------------------------------

    def test_duplicate_plugin_registration_raises(self) -> None:
        reg = FactorRegistry()
        model = _TestSignal(FactorMetadata(name="test"))
        reg.register_signal("dup", model)

        with pytest.raises(ValueError, match="Factor 'dup' already registered"):
            PluginRegistry().register_factor("dup", _OtherSignal)

    # ----------------------------------------------------------------
    # Existing FactorRegistry behaviours still pass
    # ----------------------------------------------------------------

    def test_existing_register_and_get_bridge(self) -> None:
        reg = FactorRegistry()
        from polymind.core.intents import StrategyIntent
        from polymind.core.portfolio import PortfolioTarget
        from polymind.factors.registry import FactorExecutionBridge

        class TestBridge(FactorExecutionBridge):
            async def to_order_intents(self, target: PortfolioTarget) -> list[StrategyIntent]:
                return []

        bridge = TestBridge()
        reg.register_bridge("test", bridge)
        assert reg.get_bridge("test") is bridge

    def test_existing_remove_signal(self) -> None:
        reg = FactorRegistry()
        model = _TestSignal(FactorMetadata(name="x"))
        reg.register_signal("x", model)
        reg.remove_signal("x")
        assert reg.get_signal("x") is None

    def test_existing_remove_bridge(self) -> None:
        reg = FactorRegistry()
        from polymind.core.intents import StrategyIntent
        from polymind.core.portfolio import PortfolioTarget
        from polymind.factors.registry import FactorExecutionBridge

        class TestBridge(FactorExecutionBridge):
            async def to_order_intents(self, target: PortfolioTarget) -> list[StrategyIntent]:
                return []

        bridge = TestBridge()
        reg.register_bridge("x", bridge)
        reg.remove_bridge("x")
        assert reg.get_bridge("x") is None

    def test_existing_list_bridges(self) -> None:
        reg = FactorRegistry()
        assert reg.list_bridges() == []
