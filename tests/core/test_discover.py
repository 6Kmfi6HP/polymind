"""Tests for entry point plugin discovery."""

from unittest.mock import MagicMock, patch

import pytest

from polymind.core.discover import (
    discover_all,
    discover_factors,
    discover_strategies,
    discover_workflows,
)


class _DummyStrategy:
    pass


class _DummyFactor:
    pass


class _DummyWorkflow:
    pass


class _FailingEntryPoint:
    """Simulates an entry point whose ``.load()`` raises an exception."""

    name = "broken_plugin"

    @staticmethod
    def load() -> type:
        msg = "Dependency not installed"
        raise ImportError(msg)


class TestDiscoverStrategies:
    """Tests for ``discover_strategies``."""

    def test_empty(self) -> None:
        """When no entry points, returns empty dict."""
        with patch("polymind.core.discover.entry_points") as mock_ep:
            mock_ep.return_value = []
            result = discover_strategies()
            assert result == {}

    def test_with_plugins(self) -> None:
        """When entry points exist, returns discovered plugins."""
        ep = MagicMock()
        ep.name = "test_strat"
        ep.load.return_value = _DummyStrategy

        with patch("polymind.core.discover.entry_points") as mock_ep:
            mock_ep.return_value = [ep]
            result = discover_strategies()

            assert result == {"test_strat": _DummyStrategy}

    def test_uses_correct_group(self) -> None:
        """Verifies the correct entry point group is queried."""
        with patch("polymind.core.discover.entry_points") as mock_ep:
            mock_ep.return_value = []
            discover_strategies()
            mock_ep.assert_called_once_with(group="polymind.strategies")

    def test_skips_failing_entry_points(self) -> None:
        """Entry points that fail to load are skipped gracefully."""
        good_ep = MagicMock()
        good_ep.name = "good_strat"
        good_ep.load.return_value = _DummyStrategy

        broken_ep = _FailingEntryPoint()

        with patch("polymind.core.discover.entry_points") as mock_ep:
            mock_ep.return_value = [broken_ep, good_ep]
            result = discover_strategies()

            assert result == {"good_strat": _DummyStrategy}


class TestDiscoverFactors:
    """Tests for ``discover_factors``."""

    def test_empty(self) -> None:
        with patch("polymind.core.discover.entry_points") as mock_ep:
            mock_ep.return_value = []
            result = discover_factors()
            assert result == {}

    def test_with_plugins(self) -> None:
        ep = MagicMock()
        ep.name = "test_factor"
        ep.load.return_value = _DummyFactor

        with patch("polymind.core.discover.entry_points") as mock_ep:
            mock_ep.return_value = [ep]
            result = discover_factors()

            assert result == {"test_factor": _DummyFactor}

    def test_uses_correct_group(self) -> None:
        with patch("polymind.core.discover.entry_points") as mock_ep:
            mock_ep.return_value = []
            discover_factors()
            mock_ep.assert_called_once_with(group="polymind.factors")


class TestDiscoverWorkflows:
    """Tests for ``discover_workflows``."""

    def test_empty(self) -> None:
        with patch("polymind.core.discover.entry_points") as mock_ep:
            mock_ep.return_value = []
            result = discover_workflows()
            assert result == {}

    def test_with_plugins(self) -> None:
        ep = MagicMock()
        ep.name = "test_workflow"
        ep.load.return_value = _DummyWorkflow

        with patch("polymind.core.discover.entry_points") as mock_ep:
            mock_ep.return_value = [ep]
            result = discover_workflows()

            assert result == {"test_workflow": _DummyWorkflow}

    def test_uses_correct_group(self) -> None:
        with patch("polymind.core.discover.entry_points") as mock_ep:
            mock_ep.return_value = []
            discover_workflows()
            mock_ep.assert_called_once_with(group="polymind.workflows")


class TestDiscoverAll:
    """Tests for ``discover_all``."""

    def test_returns_all_categories(self) -> None:
        """Returns structured dict of all three plugin types."""
        strat_ep = MagicMock()
        strat_ep.name = "s1"
        strat_ep.load.return_value = _DummyStrategy

        factor_ep = MagicMock()
        factor_ep.name = "f1"
        factor_ep.load.return_value = _DummyFactor

        workflow_ep = MagicMock()
        workflow_ep.name = "w1"
        workflow_ep.load.return_value = _DummyWorkflow

        # Return different results based on the group kwarg
        def _side_effect(*, group: str) -> list:
            mapping = {
                "polymind.strategies": [strat_ep],
                "polymind.factors": [factor_ep],
                "polymind.workflows": [workflow_ep],
            }
            return mapping.get(group, [])

        with patch("polymind.core.discover.entry_points") as mock_ep:
            mock_ep.side_effect = _side_effect
            result = discover_all()

            assert result == {
                "strategies": {"s1": _DummyStrategy},
                "factors": {"f1": _DummyFactor},
                "workflows": {"w1": _DummyWorkflow},
            }

    def test_empty_all(self) -> None:
        """When no entry points, returns empty sub-dicts."""
        with patch("polymind.core.discover.entry_points") as mock_ep:
            mock_ep.return_value = []
            result = discover_all()

            assert result == {
                "strategies": {},
                "factors": {},
                "workflows": {},
            }


@pytest.fixture
def mock_entry_points() -> MagicMock:
    """Fixture providing a patched ``entry_points`` mock.

    Use in tests by applying ``@patch("polymind.core.discover.entry_points")``
    or by nesting in a ``with`` block.  This fixture exists as a convenience
    for tests that want to share a mock instance.
    """
    with patch("polymind.core.discover.entry_points") as m:
        yield m
