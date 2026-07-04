"""
Shared pytest fixtures and configuration for all polymind tests.

This module is automatically loaded by pytest and provides fixtures
that are available to every test file without explicit import.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest


@pytest.fixture
def async_mock() -> type[AsyncMock]:
    """Return the AsyncMock class for creating async mocks in tests."""
    return AsyncMock


@pytest.fixture
def mock_client() -> MagicMock:
    """Create a generic mock PolymarketClient-like object with async methods."""
    client = MagicMock()
    client.get_markets = AsyncMock(return_value=[])
    client.get_balance = AsyncMock(return_value=10_000.0)
    client.get_positions = AsyncMock(return_value=[])
    client.place_order = AsyncMock()
    client.cancel_order = AsyncMock(return_value=True)
    client.cancel_all_orders = AsyncMock(return_value=0)
    client.close = AsyncMock()
    return client
