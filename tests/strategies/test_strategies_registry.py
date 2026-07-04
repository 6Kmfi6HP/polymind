"""
Tests for wiring PluginRegistry into the strategy registry.
"""

from __future__ import annotations

import pytest

from polymind.core.plugin import PluginRegistry
from polymind.core.strategy import BaseMMStrategy
from polymind.strategies import (
    get_strategy,
    list_strategies,
    register,
    register_builtin_strategies,
)


@pytest.fixture
def reset_plugin():
    """Reset PluginRegistry for test isolation and restore builtins."""
    PluginRegistry.reset()
    yield
    PluginRegistry.reset()
    register_builtin_strategies()


class _TestStrat(BaseMMStrategy):
    """A minimal strategy for testing."""

    __doc__ = "Test strategy"

    async def analyze(self, market):  # noqa
        return None


class _FallbackStrat(BaseMMStrategy):
    """Strategy only in PluginRegistry."""

    __doc__ = "Fallback strategy"

    async def analyze(self, market):  # noqa
        return None


class TestRegisterWithPluginRegistry:
    """register() decorator also registers with PluginRegistry."""

    def test_register_adds_to_plugin_registry(self, reset_plugin):
        """Decorator registers class in both _registry and PluginRegistry."""
        register("test1")(_TestStrat)

        cls = PluginRegistry().get_strategy("test1")
        assert cls is _TestStrat


class TestGetStrategyFallback:
    """get_strategy() falls back to PluginRegistry."""

    def test_get_strategy_from_plugin_registry(self, reset_plugin):
        """Retrieves strategy registered only in PluginRegistry."""
        PluginRegistry().register_strategy("fallback", _FallbackStrat)

        instance = get_strategy("fallback")
        assert isinstance(instance, _FallbackStrat)

    def test_get_strategy_prefers_local_registry(self, reset_plugin):
        """Local _registry takes priority over PluginRegistry."""
        PluginRegistry().register_strategy("override", _FallbackStrat)

        class _OverrideStrat(BaseMMStrategy):
            __doc__ = "Override"

            async def analyze(self, market):  # noqa
                return None

        register("override")(_OverrideStrat)

        instance = get_strategy("override")
        assert isinstance(instance, _OverrideStrat)

    def test_get_strategy_unknown_raises(self):
        """Raises ValueError for names in neither registry."""
        with pytest.raises(ValueError, match="Unknown strategy 'nonexistent'"):
            get_strategy("nonexistent")


class TestListStrategiesMerge:
    """list_strategies() merges both registries."""

    def test_list_includes_plugin_only(self, reset_plugin):
        """Strategies only in PluginRegistry appear in listing."""
        PluginRegistry().register_strategy("plugin_only", _FallbackStrat)

        result = list_strategies()
        assert "plugin_only" in result

    def test_list_no_duplicates(self, reset_plugin):
        """A strategy in both registries appears only once."""
        register("shared")(_TestStrat)

        result = list_strategies()
        assert "shared" in result
        count = sum(1 for key in result if key == "shared")
        assert count == 1


class TestRegisterBuiltinStrategies:
    """register_builtin_strategies() registers known strategies."""

    def test_builtins_registered(self):
        """Built-in strategies are registered by default."""
        result = list_strategies()
        assert "amm" in result
        assert "bands" in result
        assert "classic_mm" in result

    def test_builtins_in_plugin_registry(self):
        """Built-in strategies are also in PluginRegistry."""
        assert PluginRegistry().get_strategy("amm") is not None
        assert PluginRegistry().get_strategy("bands") is not None
        assert PluginRegistry().get_strategy("classic_mm") is not None

    def test_register_builtin_is_idempotent(self):
        """Calling register_builtin_strategies() again does not raise."""
        register_builtin_strategies()


class TestDuplicateRegistration:
    """Duplicate registration raises ValueError from PluginRegistry."""

    def test_register_duplicate_raises_value_error(self, reset_plugin):
        """Registering directly via PluginRegistry with an existing name raises."""
        PluginRegistry().register_strategy("dup", _FallbackStrat)

        with pytest.raises(ValueError, match="Strategy 'dup' already registered"):
            PluginRegistry().register_strategy("dup", _TestStrat)

    def test_register_decorator_is_idempotent(self, reset_plugin):
        """register() decorator does not raise on re-registration."""
        register("idem")(_TestStrat)
        # Second call should not raise since decorator guards against it
        register("idem")(_TestStrat)
