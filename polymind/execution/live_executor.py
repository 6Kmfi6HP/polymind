"""Live executor that places orders on the real Polymarket CLOB."""

from __future__ import annotations

from typing import Any

from polymind.core.intents import IntentExecutor, StrategyIntent
from polymind.polymarket.client import PolymarketClient
from polymind.polymarket.contracts import ContractsGateway
from polymind.polymarket.websocket import PolymarketWebSocketAdapter


class LiveExecutor(IntentExecutor):
    """Executor that places/cancels orders on the real Polymarket CLOB.

    Uses PolymarketClient for all exchange interactions. Optional WebSocket
    and ContractsGateway for enhanced functionality.
    """

    def __init__(
        self,
        client: PolymarketClient,
        ws: PolymarketWebSocketAdapter | None = None,
        contracts: ContractsGateway | None = None,
    ) -> None:
        self.client = client
        self.ws = ws
        self.contracts = contracts

    async def execute(self, intent: StrategyIntent) -> dict[str, Any]:
        """Execute the given intent against the real CLOB.

        Process cancellations first, then new orders.
        Returns a summary dict keyed by market_id.
        """
        results: dict[str, dict[str, Any]] = {}

        # Process cancellations
        for cancel in intent.cancels:
            market = cancel.market_id
            if market not in results:
                results[market] = {
                    "orders_placed": 0,
                    "cancellations": 0,
                    "order_ids": [],
                    "errors": [],
                }

            try:
                if cancel.order_id is not None:
                    await self.client.cancel_order(cancel.order_id)
                    results[market]["cancellations"] += 1
                else:
                    count = await self.client.cancel_all_orders(market)
                    results[market]["cancellations"] += count
            except Exception as e:
                results[market]["errors"].append(str(e))

        # Process new orders
        for order in intent.orders:
            market = order.market_id
            if market not in results:
                results[market] = {
                    "orders_placed": 0,
                    "cancellations": 0,
                    "order_ids": [],
                    "errors": [],
                }

            try:
                result = await self.client.place_order(
                    market_id=order.market_id,
                    token_id=order.outcome or "",
                    side=order.side.value if hasattr(order.side, "value") else str(order.side),
                    price=order.price,
                    size=order.size,
                    post_only=getattr(order, "post_only", True),
                )
                results[market]["orders_placed"] += 1
                results[market]["order_ids"].append(
                    result.order_id if hasattr(result, "order_id") else str(result)
                )
            except Exception as e:
                results[market]["errors"].append(str(e))

        return results

    async def shutdown(self) -> None:
        """Close all connections."""
        await self.client.close()
        if self.ws is not None:
            await self.ws.close()
        if self.contracts is not None:
            await self.contracts.close()
