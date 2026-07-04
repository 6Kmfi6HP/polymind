# Phase 18: WebSocket Enhancement & Type Unification — Implementation Plan

---

### Task 1: Create shared types module

**File:** `polymind/polymarket/types.py` (new)

Move shared types from `client.py` and `data_api.py`:
- `OrderBookLevel` (from data_api.py -> OrderLevel)
- `OrderbookSnapshot` (from data_api.py, unify with client.py OrderBookSnapshot)
- `MarketDetail` (from data_api.py)
- `Trade`, `Candle` (from data_api.py)
- `VolumeInfo` (from data_api.py)

**Changes to `client.py`**:
- Remove `OrderBookLevel`, `OrderBookSnapshot`, import from types
- Keep `MarketSummary`, `OrderResult`

**Changes to `data_api.py`**:
- Remove `OrderLevel`, `OrderbookSnapshot`, `MarketDetail`, `Candle`, `Trade`, `VolumeInfo`
- Import from types

Since this touches many files, keep backward compat — add `from polymind.polymarket.types import *` or individual imports.

---

### Task 2: Add exponential backoff + heartbeat to WebSocket

**File:** `polymind/polymarket/websocket.py` (edit)

1. Add config fields:
   - `exponential_base: float = 2.0`
   - `max_retry_delay: float = 60.0`
   - `ping_interval: float = 20.0`
   - `ping_timeout: float = 10.0`

2. Modify `_reconnect()`:
   ```python
   delay = min(self.config.reconnect_delay * (self.config.exponential_base ** self._reconnect_count), self.config.max_retry_delay)
   await asyncio.sleep(delay)
   ```

3. Add `add_callback(channel, callback)` / `remove_callback(channel, callback)`:
   - Store callbacks in `dict[WebSocketChannel, list[Callable]]`
   - In `on_events()`, after yielding event, also dispatch to registered callbacks

4. Make `on_events()` robust to unknown channels:
   - Catch `KeyError` when `channel_str.upper()` isn't in enum
   - Yield generic `MarketEvent` with `channel=None` or skip and log

---

### Task 3: Verify

- Run full test suite
- Run lint (ruff)
