"""
Tests for Polymarket client.
"""

from __future__ import annotations

import pytest

from polymind.polymarket.client import PolymarketClient


class TestPolymarketClient:
    @pytest.mark.asyncio
    async def test_init(self):
        client = PolymarketClient(private_key="0xkey")
        assert client.private_key == "0xkey"
        assert client._client is None

    @pytest.mark.asyncio
    async def test_get_markets(self):
        client = PolymarketClient()
        markets = await client.get_markets()
        assert markets == []

    @pytest.mark.asyncio
    async def test_get_positions(self):
        client = PolymarketClient()
        positions = await client.get_positions()
        assert positions == []

    @pytest.mark.asyncio
    async def test_get_balance(self):
        client = PolymarketClient()
        balance = await client.get_balance()
        assert balance == 0.0

    @pytest.mark.asyncio
    async def test_place_order(self):
        client = PolymarketClient()
        result = await client.place_order(market="0xabc", side="BUY", price=0.5, size=10)
        assert result is None

    @pytest.mark.asyncio
    async def test_cancel_order(self):
        client = PolymarketClient()
        result = await client.cancel_order("ord-123")
        assert result is True

    @pytest.mark.asyncio
    async def test_cancel_all(self):
        client = PolymarketClient()
        result = await client.cancel_all_orders()
        assert result is True

    @pytest.mark.asyncio
    async def test_close(self):
        client = PolymarketClient()
        await client.close()
        assert client._client is None
