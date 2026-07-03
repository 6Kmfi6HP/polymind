"""
Tests for strategy registry — register, get_strategy, list_strategies.
"""

from __future__ import annotations

import pytest

from polymind.core.strategy import BaseMMStrategy
from polymind.strategies import get_strategy, list_strategies, register


class SimpleStrat(BaseMMStrategy):
    """A simple test strategy."""

    async def analyze(self, market):  # noqa
        return None


class AnotherStrat(BaseMMStrategy):
    """Another test strategy."""

    async def analyze(self, market):  # noqa
        return None


class UndocStrat(BaseMMStrategy):
    """Undocumented strategy."""

    async def analyze(self, market):  # noqa
        return None


# Remove doc so we can test the empty-description branch
UndocStrat.__doc__ = None


class TestRegistry:
    """Tests for the strategy registry functions."""

    def test_register_decorator(self):
        """register() decorator registers a class by name."""

        # Make a fresh class so we don't pollute other tests
        class TempStrat(BaseMMStrategy):
            __doc__ = "Temp strategy"

            async def analyze(self, market):  # noqa
                return None

        register("temp")(TempStrat)

        # Verify the class is in the registry by instantiating
        instance = get_strategy("temp")
        assert isinstance(instance, TempStrat)

    def test_get_strategy_instantiates(self):
        """get_strategy() returns an instance when config is provided."""
        strat = get_strategy("simple", config=None)
        assert isinstance(strat, SimpleStrat)

    def test_get_strategy_unknown(self):
        """get_strategy() raises ValueError for unregistered names."""
        with pytest.raises(ValueError, match="Unknown strategy 'nope'"):
            get_strategy("nope")

    def test_list_strategies_returns_descriptions(self):
        """list_strategies() returns a dict of name -> description."""
        result = list_strategies()

        assert isinstance(result, dict)
        # Registered strategies should appear
        assert "simple" in result
        assert result["simple"] == "A simple test strategy."
        assert "another" in result
        assert result["another"] == "Another test strategy."

    def test_list_strategies_handles_none_doc(self):
        """list_strategies() returns empty string for classes with no doc."""
        result = list_strategies()

        assert "undoc" in result
        assert result["undoc"] == ""


# Register test strategies
register("simple")(SimpleStrat)
register("another")(AnotherStrat)
register("undoc")(UndocStrat)
