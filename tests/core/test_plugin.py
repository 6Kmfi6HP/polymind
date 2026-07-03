"""Tests for PluginRegistry singleton."""

import pytest

from polymind.core.plugin import PluginRegistry


class _DummyStrategy:
    pass


class _DummyFactor:
    pass


class _DummyWorkflow:
    pass


class AnotherStrategy:
    pass


class TestPluginRegistry:
    """Test suite for PluginRegistry."""

    def setup_method(self) -> None:
        """Reset registry before each test."""
        PluginRegistry.reset()

    # ----------------------------------------------------------------
    # Singleton behaviour
    # ----------------------------------------------------------------

    def test_singleton_same_instance(self) -> None:
        """Two accesses return the same registry instance."""
        reg1 = PluginRegistry()
        reg2 = PluginRegistry()
        assert reg1 is reg2

    # ----------------------------------------------------------------
    # Register and retrieve each type
    # ----------------------------------------------------------------

    def test_register_and_get_strategy(self) -> None:
        reg = PluginRegistry()
        reg.register_strategy("dummy", _DummyStrategy)
        assert reg.get_strategy("dummy") is _DummyStrategy

    def test_register_and_get_factor(self) -> None:
        reg = PluginRegistry()
        reg.register_factor("dummy", _DummyFactor)
        assert reg.get_factor("dummy") is _DummyFactor

    def test_register_and_get_workflow(self) -> None:
        reg = PluginRegistry()
        reg.register_workflow("dummy", _DummyWorkflow)
        assert reg.get_workflow("dummy") is _DummyWorkflow

    # ----------------------------------------------------------------
    # Duplicate registration raises ValueError
    # ----------------------------------------------------------------

    def test_duplicate_strategy_raises(self) -> None:
        reg = PluginRegistry()
        reg.register_strategy("dup", _DummyStrategy)
        with pytest.raises(ValueError, match="Strategy 'dup' already registered"):
            reg.register_strategy("dup", AnotherStrategy)

    def test_duplicate_factor_raises(self) -> None:
        reg = PluginRegistry()
        reg.register_factor("dup", _DummyFactor)
        with pytest.raises(ValueError, match="Factor 'dup' already registered"):
            reg.register_factor("dup", _DummyFactor)

    def test_duplicate_workflow_raises(self) -> None:
        reg = PluginRegistry()
        reg.register_workflow("dup", _DummyWorkflow)
        with pytest.raises(ValueError, match="Workflow 'dup' already registered"):
            reg.register_workflow("dup", _DummyWorkflow)

    # ----------------------------------------------------------------
    # Get returns None for unknown names
    # ----------------------------------------------------------------

    def test_get_strategy_unknown(self) -> None:
        assert PluginRegistry().get_strategy("nope") is None

    def test_get_factor_unknown(self) -> None:
        assert PluginRegistry().get_factor("nope") is None

    def test_get_workflow_unknown(self) -> None:
        assert PluginRegistry().get_workflow("nope") is None

    # ----------------------------------------------------------------
    # List returns copies (not affected by clear / external mutation)
    # ----------------------------------------------------------------

    def test_list_strategies_returns_copy(self) -> None:
        reg = PluginRegistry()
        reg.register_strategy("s1", _DummyStrategy)
        d = reg.list_strategies()
        d.clear()
        assert "s1" in reg.list_strategies()

    def test_list_factors_returns_copy(self) -> None:
        reg = PluginRegistry()
        reg.register_factor("f1", _DummyFactor)
        d = reg.list_factors()
        d.clear()
        assert "f1" in reg.list_factors()

    def test_list_workflows_returns_copy(self) -> None:
        reg = PluginRegistry()
        reg.register_workflow("w1", _DummyWorkflow)
        d = reg.list_workflows()
        d.clear()
        assert "w1" in reg.list_workflows()

    # ----------------------------------------------------------------
    # Reset works
    # ----------------------------------------------------------------

    def test_reset_clears_strategies(self) -> None:
        reg = PluginRegistry()
        reg.register_strategy("x", _DummyStrategy)
        PluginRegistry.reset()
        assert PluginRegistry().get_strategy("x") is None

    def test_reset_clears_factors(self) -> None:
        reg = PluginRegistry()
        reg.register_factor("x", _DummyFactor)
        PluginRegistry.reset()
        assert PluginRegistry().get_factor("x") is None

    def test_reset_clears_workflows(self) -> None:
        reg = PluginRegistry()
        reg.register_workflow("x", _DummyWorkflow)
        PluginRegistry.reset()
        assert PluginRegistry().get_workflow("x") is None

    def test_reset_produces_fresh_instance(self) -> None:
        reg1 = PluginRegistry()
        PluginRegistry.reset()
        reg2 = PluginRegistry()
        assert reg1 is not reg2

    # ----------------------------------------------------------------
    # Cross-type isolation
    # ----------------------------------------------------------------

    def test_registries_isolated_by_type(self) -> None:
        reg = PluginRegistry()
        reg.register_strategy("shared", _DummyStrategy)
        reg.register_factor("shared", _DummyFactor)
        reg.register_workflow("shared", _DummyWorkflow)
        assert reg.get_strategy("shared") is _DummyStrategy
        assert reg.get_factor("shared") is _DummyFactor
        assert reg.get_workflow("shared") is _DummyWorkflow
