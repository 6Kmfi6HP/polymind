> **Status:** Superseded by [`docs/architecture.md`](../../architecture.md) and [`docs/architecture/decisions/`](../../architecture/decisions/). This spec was a design document and is kept for historical reference only.

# Phase 18: WebSocket Enhancement — Design

**Status:** Design
**Date:** 2026-07-04

## Overview

`websocket.py` has a working connection lifecycle and event streaming, but lacks
production features: exponential backoff, heartbeat/ping keepalive, callback dispatch,
and robust channel parsing.

## Changes

**WebSocketConfig** add:
- `exponential_base: float = 2.0`
- `max_retry_delay: float = 60.0`
- `ping_interval: float = 20.0`
- `ping_timeout: float = 10.0`

**PolymarketWebSocketAdapter** add:
- Exponential backoff in `_reconnect()`
- `_heartbeat_task` for periodic ping/pong
- `add_callback(channel, callback)` / `remove_callback(channel, callback)` for callback dispatch
- `on_events()`: safer channel parsing (handle unknown channels, skip gracefully)
