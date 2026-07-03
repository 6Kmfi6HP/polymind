"""WebSocket adapter for Polymarket's real-time data feed."""

from __future__ import annotations

import asyncio
import json
from collections import defaultdict
from collections.abc import AsyncGenerator
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Any

from websockets.asyncio.client import connect as ws_connect
from websockets.exceptions import ConnectionClosed
from websockets.protocol import State


class WebSocketChannel(Enum):
    """Channels available on the Polymarket WebSocket feed."""

    USER_FILL = auto()
    USER_ORDER = auto()
    BOOK = auto()
    TICKER = auto()
    LAST_TRADE_PRICE = auto()


@dataclass
class WebSocketConfig:
    """Configuration for the WebSocket adapter."""

    url: str
    channels: list[WebSocketChannel] = field(default_factory=list)
    auth_token: str | None = None
    reconnect_delay: float = 1.0
    max_reconnects: int = 5


@dataclass(frozen=True)
class MarketEvent:
    """A single event received from the Polymarket WebSocket feed."""

    market_id: str
    channel: WebSocketChannel
    event_type: str
    data: dict
    timestamp: datetime


class PolymarketWebSocketAdapter:
    """WebSocket adapter for real-time Polymarket market data and user events.

    Manages connection lifecycle, channel subscriptions, automatic reconnection,
    and delivers parsed MarketEvent objects via an async generator.
    """

    def __init__(self, config: WebSocketConfig) -> None:
        self.config = config
        self._ws: Any | None = None
        self._ws_conn: Any | None = None
        self._subscriptions: dict[WebSocketChannel, set[str]] = defaultdict(set)
        self._running = False
        self._reconnect_count = 0

    async def connect(self) -> None:
        """Establish the WebSocket connection with optional authentication."""
        self._ws_conn = ws_connect(self.config.url)
        self._ws = await self._ws_conn.__aenter__()
        if self.config.auth_token:
            await self._send_json(
                {
                    "type": "auth",
                    "token": self.config.auth_token,
                }
            )

    async def subscribe(self, channel: WebSocketChannel, market_ids: list[str]) -> None:
        """Subscribe to *channel* for the given *market_ids*."""
        msg = {
            "type": "subscribe",
            "channel": channel.name.lower(),
            "market_ids": market_ids,
        }
        await self._send_json(msg)
        self._subscriptions[channel].update(market_ids)

    async def unsubscribe(self, channel: WebSocketChannel, market_ids: list[str]) -> None:
        """Unsubscribe *channel* for the given *market_ids*."""
        msg = {
            "type": "unsubscribe",
            "channel": channel.name.lower(),
            "market_ids": market_ids,
        }
        await self._send_json(msg)
        remaining = self._subscriptions[channel] - set(market_ids)
        if remaining:
            self._subscriptions[channel] = remaining
        else:
            del self._subscriptions[channel]

    async def on_events(self) -> AsyncGenerator[MarketEvent, None]:
        """Yield parsed ``MarketEvent`` instances as they arrive.

        Handles automatic reconnection on unexpected disconnects and
        cleanly exits when :meth:`close` is called.
        """
        self._running = True
        while self._running and self._ws is not None:
            try:
                message = await self._ws.recv()
                data = json.loads(message)
                msg_type = data.get("type", "unknown")
                channel_str = data.get("channel", "unknown")
                market_id = data.get("market", data.get("market_id", ""))
                channel = WebSocketChannel[channel_str.upper()]
                event = MarketEvent(
                    market_id=market_id,
                    channel=channel,
                    event_type=msg_type,
                    data=data,
                    timestamp=datetime.utcnow(),
                )
                yield event
            except ConnectionClosed:
                if self._running:
                    await self._reconnect()
                    continue
                break
            except StopAsyncIteration:
                break
            except Exception:
                if not self._running:
                    break
                raise

    async def _reconnect(self) -> None:
        """Attempt to reconnect and re-subscribe after a disconnect."""
        self._reconnect_count += 1
        if self._reconnect_count > self.config.max_reconnects:
            self._running = False
            return
        await asyncio.sleep(self.config.reconnect_delay)
        try:
            await self.connect()
        except Exception:
            return
        for channel, market_ids in dict(self._subscriptions).items():
            await self.subscribe(channel, list(market_ids))

    async def _send_json(self, data: dict) -> None:
        """Encode *data* as JSON and send over the WebSocket connection."""
        if self._ws is not None:
            await self._ws.send(json.dumps(data))

    async def close(self) -> None:
        """Gracefully shut down the WebSocket and reset adapter state."""
        self._running = False
        if self._ws is not None:
            await self._ws.close()
            self._ws = None
        if self._ws_conn is not None:
            await self._ws_conn.__aexit__(None, None, None)
            self._ws_conn = None
        self._subscriptions.clear()
        self._reconnect_count = 0

    @property
    def connected(self) -> bool:
        """Return ``True`` if the WebSocket connection is currently open."""
        return self._ws is not None and self._ws.state is State.OPEN

    @property
    def active_subscriptions(self) -> dict[WebSocketChannel, set[str]]:
        """Return a snapshot of currently tracked subscriptions."""
        return {k: set(v) for k, v in self._subscriptions.items()}

    async def __aenter__(self) -> PolymarketWebSocketAdapter:
        await self.connect()
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()
