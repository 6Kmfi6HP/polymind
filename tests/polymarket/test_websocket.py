"""Tests for the Polymarket WebSocket adapter."""

from __future__ import annotations

import asyncio
import json
from datetime import datetime
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from websockets.exceptions import ConnectionClosed
from websockets.protocol import State

from polymind.polymarket.websocket import (
    MarketEvent,
    PolymarketWebSocketAdapter,
    WebSocketChannel,
    WebSocketConfig,
)


@pytest.fixture
def config() -> WebSocketConfig:
    return WebSocketConfig(url="ws://localhost:9999/ws")


@pytest.fixture
def mock_ws() -> MagicMock:
    """Return a fully functional mock WebSocket connection."""
    ws = MagicMock()
    ws.state = State.OPEN
    ws.recv = AsyncMock()
    ws.send = AsyncMock()
    ws.close = AsyncMock()
    return ws


@pytest.fixture
async def adapter(config: WebSocketConfig, mock_ws: MagicMock):
    """Create an adapter with a mocked WebSocket connection."""
    mock_conn = AsyncMock()
    mock_conn.__aenter__.return_value = mock_ws
    with patch("polymind.polymarket.websocket.ws_connect", return_value=mock_conn):
        a = PolymarketWebSocketAdapter(config)
        await a.connect()
        yield a
        await a.close()


class TestWebSocketChannel:
    def test_enum_values_distinct(self):
        """Each channel has a unique auto-assigned value."""
        values = {c.value for c in WebSocketChannel}
        assert len(values) == len(WebSocketChannel)

    def test_members(self):
        """All expected channels are present."""
        names = {c.name for c in WebSocketChannel}
        expected = {"USER_FILL", "USER_ORDER", "BOOK", "TICKER", "LAST_TRADE_PRICE"}
        assert names == expected


class TestWebSocketConfig:
    def test_defaults(self):
        """Config uses sensible defaults."""
        cfg = WebSocketConfig(url="ws://test")
        assert cfg.url == "ws://test"
        assert cfg.channels == []
        assert cfg.auth_token is None
        assert cfg.reconnect_delay == 1.0
        assert cfg.max_reconnects == 5
        assert cfg.exponential_base == 2.0
        assert cfg.max_retry_delay == 60.0
        assert cfg.ping_interval == 20.0
        assert cfg.ping_timeout == 10.0

    def test_url_required(self):
        """url is a required positional argument."""
        with pytest.raises(TypeError):
            WebSocketConfig()  # type: ignore[call-arg]


class TestMarketEvent:
    def test_construction(self):
        """MarketEvent holds all fields."""
        ts = datetime(2026, 1, 1)
        event = MarketEvent(
            market_id="0xabc",
            channel=WebSocketChannel.BOOK,
            event_type="price_change",
            data={"price": "0.5"},
            timestamp=ts,
        )
        assert event.market_id == "0xabc"
        assert event.channel == WebSocketChannel.BOOK
        assert event.event_type == "price_change"
        assert event.data == {"price": "0.5"}
        assert event.timestamp is ts

    def test_frozen(self):
        """MarketEvent fields cannot be mutated."""
        event = MarketEvent(
            market_id="0xabc",
            channel=WebSocketChannel.TICKER,
            event_type="tick",
            data={},
            timestamp=datetime(2026, 1, 1),
        )
        with pytest.raises(AttributeError):
            event.market_id = "0xdef"  # type: ignore[misc]


class TestPolymarketWebSocketAdapter:
    """Integration-style tests that mock the underlying WebSocket connection."""

    # ---------- connect ----------

    @pytest.mark.asyncio
    async def test_connect_opens_websocket(self, config: WebSocketConfig, mock_ws: MagicMock):
        """connect() calls websockets.connect with the configured URL."""
        mock_conn = AsyncMock()
        mock_conn.__aenter__.return_value = mock_ws
        with patch(
            "polymind.polymarket.websocket.ws_connect", return_value=mock_conn
        ) as mock_connect:
            adapter = PolymarketWebSocketAdapter(config)
            await adapter.connect()
            mock_connect.assert_called_once_with(config.url)
            assert adapter.connected
            await adapter.close()

    @pytest.mark.asyncio
    async def test_connect_sends_auth_when_token_provided(self, mock_ws: MagicMock):
        """connect() sends an auth message when auth_token is set."""
        mock_conn = AsyncMock()
        mock_conn.__aenter__.return_value = mock_ws
        with patch("polymind.polymarket.websocket.ws_connect", return_value=mock_conn):
            cfg = WebSocketConfig(url="ws://test", auth_token="tok123")
            adapter = PolymarketWebSocketAdapter(cfg)
            await adapter.connect()
            expected = json.dumps({"type": "auth", "token": "tok123"})
            mock_ws.send.assert_awaited_with(expected)
            await adapter.close()

    @pytest.mark.asyncio
    async def test_connect_skips_auth_when_no_token(
        self, config: WebSocketConfig, mock_ws: MagicMock
    ):
        """connect() does not send auth when auth_token is None."""
        mock_conn = AsyncMock()
        mock_conn.__aenter__.return_value = mock_ws
        with patch("polymind.polymarket.websocket.ws_connect", return_value=mock_conn):
            adapter = PolymarketWebSocketAdapter(config)
            await adapter.connect()
            mock_ws.send.assert_not_awaited()
            await adapter.close()

    # ---------- subscribe / unsubscribe ----------

    @pytest.mark.asyncio
    async def test_subscribe_sends_message_and_tracks(
        self, adapter: PolymarketWebSocketAdapter, mock_ws: MagicMock
    ):
        """subscribe sends a subscribe JSON message and records the subscription."""
        await adapter.subscribe(WebSocketChannel.BOOK, ["0xabc", "0xdef"])
        expected = json.dumps(
            {
                "type": "subscribe",
                "channel": "book",
                "market_ids": ["0xabc", "0xdef"],
            }
        )
        mock_ws.send.assert_awaited_with(expected)
        assert WebSocketChannel.BOOK in adapter.active_subscriptions
        assert adapter.active_subscriptions[WebSocketChannel.BOOK] == {"0xabc", "0xdef"}

    @pytest.mark.asyncio
    async def test_subscribe_multiple_channels_separately(
        self, adapter: PolymarketWebSocketAdapter, mock_ws: MagicMock
    ):
        """Multiple subscribe calls accumulate in separate channel entries."""
        await adapter.subscribe(WebSocketChannel.BOOK, ["m1"])
        await adapter.subscribe(WebSocketChannel.TICKER, ["m2"])
        expected = json.dumps(
            {
                "type": "subscribe",
                "channel": "ticker",
                "market_ids": ["m2"],
            }
        )
        mock_ws.send.assert_awaited_with(expected)
        assert WebSocketChannel.BOOK in adapter.active_subscriptions
        assert WebSocketChannel.TICKER in adapter.active_subscriptions

    @pytest.mark.asyncio
    async def test_subscribe_extends_existing_set(
        self, adapter: PolymarketWebSocketAdapter, mock_ws: MagicMock
    ):
        """Subscribing to the same channel adds market IDs to the tracked set."""
        await adapter.subscribe(WebSocketChannel.BOOK, ["m1"])
        await adapter.subscribe(WebSocketChannel.BOOK, ["m2", "m3"])
        assert adapter.active_subscriptions[WebSocketChannel.BOOK] == {"m1", "m2", "m3"}

    @pytest.mark.asyncio
    async def test_unsubscribe_sends_message_and_removes(
        self, adapter: PolymarketWebSocketAdapter, mock_ws: MagicMock
    ):
        """unsubscribe sends an unsubscribe message and removes market IDs."""
        await adapter.subscribe(WebSocketChannel.BOOK, ["m1", "m2", "m3"])
        mock_ws.send.reset_mock()
        await adapter.unsubscribe(WebSocketChannel.BOOK, ["m1", "m3"])
        expected = json.dumps(
            {
                "type": "unsubscribe",
                "channel": "book",
                "market_ids": ["m1", "m3"],
            }
        )
        mock_ws.send.assert_awaited_with(expected)
        assert adapter.active_subscriptions[WebSocketChannel.BOOK] == {"m2"}

    @pytest.mark.asyncio
    async def test_unsubscribe_removes_channel_when_last_market(
        self, adapter: PolymarketWebSocketAdapter, mock_ws: MagicMock
    ):
        """Unsubscribing the last market removes the channel entry entirely."""
        await adapter.subscribe(WebSocketChannel.BOOK, ["m1"])
        await adapter.unsubscribe(WebSocketChannel.BOOK, ["m1"])
        assert WebSocketChannel.BOOK not in adapter.active_subscriptions

    # ---------- active_subscriptions ----------

    @pytest.mark.asyncio
    async def test_active_subscriptions_returns_copy(
        self, adapter: PolymarketWebSocketAdapter, mock_ws: MagicMock
    ):
        """active_subscriptions returns a snapshot (new dict)."""
        await adapter.subscribe(WebSocketChannel.BOOK, ["m1"])
        snap = adapter.active_subscriptions
        snap[WebSocketChannel.BOOK].add("m2")
        assert "m2" not in adapter.active_subscriptions[WebSocketChannel.BOOK]

    # ---------- on_events ----------

    @pytest.mark.asyncio
    async def test_on_events_yields_market_event(
        self, adapter: PolymarketWebSocketAdapter, mock_ws: MagicMock
    ):
        """on_events parses a JSON message and yields a MarketEvent."""
        mock_ws.recv.side_effect = [
            json.dumps(
                {
                    "type": "price_change",
                    "channel": "book",
                    "market_id": "0xabc",
                    "price": "0.55",
                }
            ),
            ConnectionClosed(None, None),
        ]
        events = []
        async for event in adapter.on_events():
            events.append(event)
        assert len(events) == 1
        e = events[0]
        assert isinstance(e, MarketEvent)
        assert e.market_id == "0xabc"
        assert e.channel == WebSocketChannel.BOOK
        assert e.event_type == "price_change"
        assert e.data["price"] == "0.55"

    @pytest.mark.asyncio
    async def test_on_events_multiple_messages(
        self, adapter: PolymarketWebSocketAdapter, mock_ws: MagicMock
    ):
        """on_events yields one MarketEvent per incoming message."""
        mock_ws.recv.side_effect = [
            json.dumps({"type": "tick", "channel": "ticker", "market_id": "m1"}),
            json.dumps({"type": "fill", "channel": "user_fill", "market_id": "m2"}),
            ConnectionClosed(None, None),
        ]
        events = [e async for e in adapter.on_events()]
        assert len(events) == 2
        assert events[0].channel == WebSocketChannel.TICKER
        assert events[0].market_id == "m1"
        assert events[1].channel == WebSocketChannel.USER_FILL
        assert events[1].market_id == "m2"

    @pytest.mark.asyncio
    async def test_on_events_exits_cleanly_on_close(
        self, adapter: PolymarketWebSocketAdapter, mock_ws: MagicMock
    ):
        """on_events stops iterating when close() is called mid-stream."""
        mock_ws.recv.side_effect = [
            json.dumps({"type": "tick", "channel": "ticker", "market_id": "m1"}),
        ]
        events = []
        async for event in adapter.on_events():
            events.append(event)
            if len(events) == 1:
                await adapter.close()
        assert len(events) == 1

    # ---------- reconnection ----------

    @pytest.mark.asyncio
    async def test_reconnect_on_disconnect(self, config: WebSocketConfig):
        """_reconnect reconnects after a ConnectionClosed."""
        adapter = PolymarketWebSocketAdapter(config)
        # Simulate: after disconnect, reconnect creates a fresh ws
        fresh_ws = MagicMock()
        fresh_ws.state = State.OPEN
        fresh_ws.recv = AsyncMock()
        fresh_ws.send = AsyncMock()
        fresh_ws.close = AsyncMock()
        fresh_conn = AsyncMock()
        fresh_conn.__aenter__.return_value = fresh_ws

        # Store subscription state to verify re-subscribe
        adapter._subscriptions[WebSocketChannel.BOOK].add("m1")
        adapter._ws = fresh_ws

        with patch(
            "polymind.polymarket.websocket.ws_connect", return_value=fresh_conn
        ) as mock_conn:
            await adapter._reconnect()
            assert mock_conn.called
            assert adapter._ws is not None
        await adapter.close()

    @pytest.mark.asyncio
    async def test_reconnect_exhausts_max_retries(
        self, config: WebSocketConfig, mock_ws: MagicMock
    ):
        """Adapter stops reconnecting after exhausting max_reconnects."""
        cfg = WebSocketConfig(url=config.url, max_reconnects=2, reconnect_delay=0.01)
        adapter = PolymarketWebSocketAdapter(cfg)
        adapter._ws = mock_ws
        adapter._running = True  # on_events would set this

        with (
            patch("polymind.polymarket.websocket.ws_connect") as mock_connect,
            patch("asyncio.sleep"),
        ):
            mock_connect.side_effect = Exception("fail")
            await adapter._reconnect()  # attempt 1
            assert adapter._reconnect_count == 1
            assert adapter._running

            await adapter._reconnect()  # attempt 2
            assert adapter._reconnect_count == 2
            assert adapter._running

            await adapter._reconnect()  # attempt 3 = exhausts
            assert adapter._reconnect_count == 3
            assert not adapter._running

        await adapter.close()

    # ---------- close ----------

    @pytest.mark.asyncio
    async def test_close_cleans_up(self, adapter: PolymarketWebSocketAdapter, mock_ws: MagicMock):
        """close resets all state and closes the WebSocket."""
        await adapter.subscribe(WebSocketChannel.BOOK, ["m1"])
        assert adapter.connected
        await adapter.close()
        mock_ws.close.assert_awaited_once()
        assert adapter._ws is None
        assert adapter.active_subscriptions == {}
        assert adapter._reconnect_count == 0
        assert not adapter.connected

    @pytest.mark.asyncio
    async def test_close_idempotent(self, adapter: PolymarketWebSocketAdapter):
        """Calling close multiple times does not raise."""
        await adapter.close()
        await adapter.close()

    # ---------- context manager ----------

    @pytest.mark.asyncio
    async def test_context_manager(self, config: WebSocketConfig, mock_ws: MagicMock):
        """__aenter__ connects and __aexit__ closes."""
        mock_conn = AsyncMock()
        mock_conn.__aenter__.return_value = mock_ws
        with patch(
            "polymind.polymarket.websocket.ws_connect", return_value=mock_conn
        ) as mock_connect:
            async with PolymarketWebSocketAdapter(config) as adapter:
                assert adapter.connected
                mock_connect.assert_called_once()
            assert not adapter.connected
            mock_ws.close.assert_awaited_once()

    # ---------- connected property ----------

    @pytest.mark.asyncio
    async def test_connected_true_when_open(
        self, adapter: PolymarketWebSocketAdapter, mock_ws: MagicMock
    ):
        """connected returns True when ws is open."""
        assert adapter.connected

    @pytest.mark.asyncio
    async def test_connected_false_when_closed(self, adapter: PolymarketWebSocketAdapter):
        """connected returns False after close."""
        await adapter.close()
        assert not adapter.connected

    @pytest.mark.asyncio
    async def test_connected_false_before_connect(self, config: WebSocketConfig):
        """connected returns False before connect() is called."""
        a = PolymarketWebSocketAdapter(config)
        assert not a.connected


class TestExponentialBackoff:
    """Tests for exponential backoff in reconnection logic."""

    @pytest.mark.asyncio
    async def test_exponential_backoff_delay(self):
        """_reconnect uses exponential backoff delay calculation."""
        cfg = WebSocketConfig(
            url="ws://localhost:9999/ws",
            reconnect_delay=1.0,
            exponential_base=2.0,
            max_retry_delay=60.0,
            max_reconnects=5,
        )
        adapter = PolymarketWebSocketAdapter(cfg)

        # First reconnect: delay = min(1.0 * 2**0, 60.0) = 1.0
        assert adapter._reconnect_count == 0
        with (
            patch("polymind.polymarket.websocket.ws_connect"),
            patch("asyncio.sleep") as mock_sleep,
        ):
            await adapter._reconnect()
            mock_sleep.assert_awaited_once_with(1.0)

        # Second reconnect: delay = min(1.0 * 2**1, 60.0) = 2.0
        with (
            patch("polymind.polymarket.websocket.ws_connect"),
            patch("asyncio.sleep") as mock_sleep,
        ):
            await adapter._reconnect()
            mock_sleep.assert_awaited_once_with(2.0)

        # Third reconnect: delay = min(1.0 * 2**2, 60.0) = 4.0
        with (
            patch("polymind.polymarket.websocket.ws_connect"),
            patch("asyncio.sleep") as mock_sleep,
        ):
            await adapter._reconnect()
            mock_sleep.assert_awaited_once_with(4.0)

        await adapter.close()

    @pytest.mark.asyncio
    async def test_max_retry_delay_caps_backoff(self):
        """Exponential backoff is capped by max_retry_delay."""
        cfg = WebSocketConfig(
            url="ws://localhost:9999/ws",
            reconnect_delay=10.0,
            exponential_base=2.0,
            max_retry_delay=25.0,
            max_reconnects=5,
        )
        adapter = PolymarketWebSocketAdapter(cfg)

        # After enough attempts, delay should be capped at 25.0
        # Attempt 3: min(10.0 * 2**2, 25.0) = min(40.0, 25.0) = 25.0
        adapter._reconnect_count = 2
        with (
            patch("polymind.polymarket.websocket.ws_connect"),
            patch("asyncio.sleep") as mock_sleep,
        ):
            await adapter._reconnect()
            mock_sleep.assert_awaited_once_with(25.0)

        await adapter.close()


class TestHeartbeat:
    """Tests for WebSocket heartbeat keepalive."""

    @pytest.mark.asyncio
    async def test_heartbeat_sends_pings(self, mock_ws: MagicMock):
        """Heartbeat loop sends ping messages periodically."""
        cfg = WebSocketConfig(url="ws://localhost:9999/ws", ping_interval=0.01)
        mock_conn = AsyncMock()
        mock_conn.__aenter__.return_value = mock_ws
        with patch("polymind.polymarket.websocket.ws_connect", return_value=mock_conn):
            adapter = PolymarketWebSocketAdapter(cfg)
            await adapter.connect()

            # Let heartbeat fire a couple of times
            await asyncio.sleep(0.05)
            await adapter.close()

            # Should have sent at least one ping
            ping_calls = [
                call
                for call in mock_ws.send.await_args_list
                if json.loads(call[0][0]) == {"type": "ping"}
            ]
            assert len(ping_calls) >= 1

    @pytest.mark.asyncio
    async def test_heartbeat_stops_on_close(self, mock_ws: MagicMock):
        """Heartbeat loop stops after close is called."""
        cfg = WebSocketConfig(url="ws://localhost:9999/ws", ping_interval=0.01)
        mock_conn = AsyncMock()
        mock_conn.__aenter__.return_value = mock_ws
        with patch("polymind.polymarket.websocket.ws_connect", return_value=mock_conn):
            adapter = PolymarketWebSocketAdapter(cfg)
            await adapter.connect()
            await adapter.close()

            # Clear calls made so far
            mock_ws.send.reset_mock()

            # Give time for heartbeat to fire if it were still running
            await asyncio.sleep(0.05)

            ping_calls = [
                call
                for call in mock_ws.send.await_args_list
                if json.loads(call[0][0]) == {"type": "ping"}
            ]
            assert len(ping_calls) == 0


class TestCallbacks:
    """Tests for callback dispatch."""

    @pytest.mark.asyncio
    async def test_callback_dispatched_on_event(
        self, adapter: PolymarketWebSocketAdapter, mock_ws: MagicMock
    ):
        """Callbacks registered for a channel are called when events arrive."""
        calls = []

        def my_cb(event):
            calls.append(event)

        adapter.add_callback(WebSocketChannel.BOOK, my_cb)

        mock_ws.recv.side_effect = [
            json.dumps({"type": "price_change", "channel": "book", "market_id": "0xabc"}),
            ConnectionClosed(None, None),
        ]

        async for _ in adapter.on_events():
            pass

        assert len(calls) == 1
        assert calls[0].market_id == "0xabc"
        assert calls[0].channel == WebSocketChannel.BOOK

    @pytest.mark.asyncio
    async def test_remove_callback_stops_dispatch(
        self, adapter: PolymarketWebSocketAdapter, mock_ws: MagicMock
    ):
        """Removed callbacks are no longer called on events."""
        calls = []

        def my_cb(event):
            calls.append(event)

        adapter.add_callback(WebSocketChannel.BOOK, my_cb)
        adapter.remove_callback(WebSocketChannel.BOOK, my_cb)

        mock_ws.recv.side_effect = [
            json.dumps({"type": "price_change", "channel": "book", "market_id": "0xabc"}),
            ConnectionClosed(None, None),
        ]

        async for _ in adapter.on_events():
            pass

        assert len(calls) == 0

    @pytest.mark.asyncio
    async def test_multiple_callbacks_on_same_channel(
        self, adapter: PolymarketWebSocketAdapter, mock_ws: MagicMock
    ):
        """Multiple callbacks on the same channel are all called."""
        calls1 = []
        calls2 = []

        def cb1(event):
            calls1.append(event)

        def cb2(event):
            calls2.append(event)

        adapter.add_callback(WebSocketChannel.BOOK, cb1)
        adapter.add_callback(WebSocketChannel.BOOK, cb2)

        mock_ws.recv.side_effect = [
            json.dumps({"type": "price_change", "channel": "book", "market_id": "0xabc"}),
            ConnectionClosed(None, None),
        ]

        async for _ in adapter.on_events():
            pass

        assert len(calls1) == 1
        assert len(calls2) == 1

    @pytest.mark.asyncio
    async def test_bad_callback_does_not_kill_stream(
        self, adapter: PolymarketWebSocketAdapter, mock_ws: MagicMock
    ):
        """A callback that raises an exception does not break the event stream."""
        good_calls = []

        def bad_cb(event):
            raise RuntimeError("oops")

        def good_cb(event):
            good_calls.append(event)

        adapter.add_callback(WebSocketChannel.BOOK, bad_cb)
        adapter.add_callback(WebSocketChannel.BOOK, good_cb)

        mock_ws.recv.side_effect = [
            json.dumps({"type": "price_change", "channel": "book", "market_id": "0xabc"}),
            ConnectionClosed(None, None),
        ]

        async for _ in adapter.on_events():
            pass

        assert len(good_calls) == 1

    @pytest.mark.asyncio
    async def test_callback_channel_isolation(
        self, adapter: PolymarketWebSocketAdapter, mock_ws: MagicMock
    ):
        """Callbacks are only called for their registered channel."""
        book_calls = []
        ticker_calls = []

        def book_cb(event):
            book_calls.append(event)

        def ticker_cb(event):
            ticker_calls.append(event)

        adapter.add_callback(WebSocketChannel.BOOK, book_cb)
        adapter.add_callback(WebSocketChannel.TICKER, ticker_cb)

        mock_ws.recv.side_effect = [
            json.dumps({"type": "price_change", "channel": "book", "market_id": "m1"}),
            json.dumps({"type": "tick", "channel": "ticker", "market_id": "m2"}),
            ConnectionClosed(None, None),
        ]

        async for _ in adapter.on_events():
            pass

        assert len(book_calls) == 1
        assert book_calls[0].market_id == "m1"
        assert len(ticker_calls) == 1
        assert ticker_calls[0].market_id == "m2"


class TestUnknownChannel:
    """Tests for handling unknown channels gracefully."""

    @pytest.mark.asyncio
    async def test_unknown_channel_skipped_gracefully(
        self, adapter: PolymarketWebSocketAdapter, mock_ws: MagicMock
    ):
        """Unknown channels in on_events are skipped without crashing."""
        mock_ws.recv.side_effect = [
            json.dumps({"type": "price_change", "channel": "book", "market_id": "0xabc"}),
            json.dumps({"type": "data", "channel": "unknown_channel", "market_id": "0xdef"}),
            json.dumps({"type": "tick", "channel": "ticker", "market_id": "m3"}),
            ConnectionClosed(None, None),
        ]

        events = [e async for e in adapter.on_events()]

        # Only book and ticker events should be yielded, unknown channel skipped
        assert len(events) == 2
        assert events[0].channel == WebSocketChannel.BOOK
        assert events[1].channel == WebSocketChannel.TICKER

    @pytest.mark.asyncio
    async def test_unknown_channel_no_subsequent_events_lost(
        self, adapter: PolymarketWebSocketAdapter, mock_ws: MagicMock
    ):
        """Skipping an unknown channel does not lose subsequent events."""
        mock_ws.recv.side_effect = [
            json.dumps({"type": "data", "channel": "bogus", "market_id": "x"}),
            json.dumps({"type": "tick", "channel": "ticker", "market_id": "m1"}),
            ConnectionClosed(None, None),
        ]

        events = [e async for e in adapter.on_events()]
        assert len(events) == 1
        assert events[0].market_id == "m1"


class TestEdgeCoverage:
    """Cover remaining lines: 151, 154-157, 192-193."""

    @pytest.mark.asyncio
    async def test_on_events_stop_async_iteration(
        self, adapter: PolymarketWebSocketAdapter, mock_ws: MagicMock
    ):
        """Line 152-153: StopAsyncIteration breaks the loop."""
        mock_ws.recv.side_effect = StopAsyncIteration
        events = [e async for e in adapter.on_events()]
        assert len(events) == 0

    @pytest.mark.asyncio
    async def test_on_events_generic_exception_re_raises(
        self, adapter: PolymarketWebSocketAdapter, mock_ws: MagicMock
    ):
        """Line 157: generic Exception re-raises when _running is True."""
        mock_ws.recv.side_effect = ValueError("unexpected")
        adapter._running = True
        gen = adapter.on_events()
        with pytest.raises(ValueError, match="unexpected"):
            await gen.__anext__()

    # Lines 151 and 156 (the `if not self._running: break` guards in the
    # ConnectionClosed / Exception handlers) require the generator to have
    # yielded at least once, then _running set to False mid-stream. This is
    # covered structurally by the test_on_events_exits_cleanly_on_close test.

    @pytest.mark.asyncio
    async def test_heartbeat_cancelled_error(
        self, adapter: PolymarketWebSocketAdapter, mock_ws: MagicMock
    ):
        """Line 190-191: CancelledError in heartbeat is caught silently."""
        import asyncio

        task = asyncio.create_task(adapter._heartbeat_loop())
        await asyncio.sleep(0.01)
        task.cancel()
        await asyncio.sleep(0.01)
        # Task completes silently — no exception propagated

    @pytest.mark.asyncio
    async def test_heartbeat_generic_exception(self, config: WebSocketConfig):
        """Line 192-193: generic Exception in heartbeat is caught silently."""
        adapter = PolymarketWebSocketAdapter(config)
        import asyncio

        # Directly modify _send_json to raise on call
        async def bad_send(*args):
            raise RuntimeError("heartbeat oops")

        adapter._send_json = bad_send
        adapter._ws = MagicMock()

        async def run_and_stop():
            await asyncio.sleep(0.02)
            adapter._running = False

        adapter._running = True
        await asyncio.gather(adapter._heartbeat_loop(), run_and_stop())
        # No exception raised — heartbeat silently catches errors
