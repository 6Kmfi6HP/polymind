> **Status:** Superseded by [`docs/architecture.md`](../../architecture.md) and [`docs/architecture/decisions/`](../../architecture/decisions/). This spec was a design document and is kept for historical reference only.

# Phase 19: LiveExecutor — Design

**Status:** Design
**Date:** 2026-07-04

## Overview

Connect the Polymarket adapter layer (Phase 15-18) with the intent execution layer.
`LiveExecutor` implements `IntentExecutor` using `PolymarketClient` for real CLOB
order placement and cancellation.

## Architecture

```
StrategyIntent
    │
    ▼
LiveExecutor.execute(intent)
    │
    ├── cancellations → PolymarketClient.cancel_order()
    ├── orders        → PolymarketClient.place_order()
    └── summary      → {market_id: {order_id, status, ...}}
```
