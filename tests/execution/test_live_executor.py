"""Tests for LiveExecutor."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from polymind.core.intents import CancelIntent, OrderIntent, StrategyIntent
from polymind.execution.live_executor import LiveExecutor
from polymind.polymarket.client import OrderResult, PolymarketClient


class TestLiveExecutor:
    @pytest.fixture
    def mock_client(self) -> MagicMock:
        client = MagicMock(spec=PolymarketClient)
        client.place_order = AsyncMock()
        client.cancel_order = AsyncMock(return_value=True)
        client.cancel_all_orders = AsyncMock(return_value=2)
        client.close = AsyncMock()
        return client

    @pytest.fixture
    def executor(self, mock_client: MagicMock) -> LiveExecutor:
        return LiveExecutor(client=mock_client)

    @pytest.mark.asyncio
    async def test_constructor_stores_refs(self, mock_client: MagicMock):
        ex = LiveExecutor(client=mock_client)
        assert ex.client is mock_client
        assert ex.ws is None
        assert ex.contracts is None

    @pytest.mark.asyncio
    async def test_execute_empty_intent(self, executor: LiveExecutor):
        """An empty intent does nothing and returns empty results."""
        intent = StrategyIntent(
            timestamp=datetime(2026, 1, 1),
            strategy_name="test",
            orders=[],
            cancels=[],
        )
        result = await executor.execute(intent)
        assert result == {}

    @pytest.mark.asyncio
    async def test_execute_processes_cancels(self, executor: LiveExecutor, mock_client: MagicMock):
        intent = StrategyIntent(
            timestamp=datetime(2026, 1, 1),
            strategy_name="test",
            orders=[],
            cancels=[CancelIntent(market_id="0xm1", order_id="ord-1")],
        )
        result = await executor.execute(intent)
        mock_client.cancel_order.assert_awaited_once_with("ord-1")
        assert "0xm1" in result
        assert result["0xm1"]["cancellations"] == 1

    @pytest.mark.asyncio
    async def test_execute_cancel_all_for_market(
        self, executor: LiveExecutor, mock_client: MagicMock
    ):
        intent = StrategyIntent(
            timestamp=datetime(2026, 1, 1),
            strategy_name="test",
            orders=[],
            cancels=[CancelIntent(market_id="0xm1")],
        )
        result = await executor.execute(intent)
        mock_client.cancel_all_orders.assert_awaited_once_with()
        assert result["0xm1"]["cancellations"] == 2

    @pytest.mark.asyncio
    async def test_execute_places_orders(self, executor: LiveExecutor, mock_client: MagicMock):
        mock_client.place_order.return_value = OrderResult(
            order_id="ord-new-1",
            status="OPEN",
            market_id="0xm1",
            side="BUY",
            price="0.5",
            size="10",
            filled_size="0",
            remaining_size="10",
            created_at=datetime(2026, 1, 1),
        )
        intent = StrategyIntent(
            timestamp=datetime(2026, 1, 1),
            strategy_name="test",
            orders=[OrderIntent(market_id="0xm1", side="BUY", price=0.5, size=10, outcome="YES")],
            cancels=[],
        )
        result = await executor.execute(intent)
        mock_client.place_order.assert_awaited_once()
        assert result["0xm1"]["orders_placed"] == 1

    @pytest.mark.asyncio
    async def test_execute_error_does_not_crash(
        self, executor: LiveExecutor, mock_client: MagicMock
    ):
        mock_client.place_order.side_effect = Exception("CLOB timeout")
        intent = StrategyIntent(
            timestamp=datetime(2026, 1, 1),
            strategy_name="test",
            orders=[OrderIntent(market_id="0xm1", side="BUY", price=0.5, size=10, outcome="YES")],
            cancels=[],
        )
        result = await executor.execute(intent)
        assert "0xm1" in result
        assert len(result["0xm1"]["errors"]) == 1
        assert "CLOB timeout" in result["0xm1"]["errors"][0]

    @pytest.mark.asyncio
    async def test_shutdown_closes_all(self, mock_client: MagicMock):
        mock_ws = MagicMock()
        mock_ws.close = AsyncMock()
        mock_contracts = MagicMock()
        mock_contracts.close = AsyncMock()

        ex = LiveExecutor(client=mock_client, ws=mock_ws, contracts=mock_contracts)
        await ex.shutdown()

        mock_client.close.assert_awaited_once()
        mock_ws.close.assert_awaited_once()
        mock_contracts.close.assert_awaited_once()
