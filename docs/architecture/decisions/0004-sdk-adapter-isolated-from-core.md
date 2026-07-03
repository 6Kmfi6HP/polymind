# ADR 0004: SDK adapter is isolated from core

**Status:** Accepted
**Date:** 2026-07-03

## Context

Polymarket API documentation separates public market data, L1 wallet operations,
L2 order/account operations, user WebSocket authentication, builder attribution,
and contract interactions. Search and documentation review also show migration
pressure from the older `py-clob-client` toward `py-clob-client-v2` / unified SDK
semantics.

If strategy code imports SDK objects directly, SDK migration becomes a strategy
rewrite.

## Decision

The Polymarket SDK is isolated behind adapter ports. Core strategy, factor,
risk, and backtesting modules depend on project-owned interfaces and domain
objects, not concrete SDK request/response types.

## Consequences

- SDK validation is its own roadmap phase before strategy implementation.
- Auth levels are documented and tested at adapter boundaries.
- Asset IDs, condition IDs, tick sizes, order types, and auth credentials remain
  venue-adapter concerns.
- Future SDK migration should not change strategy policy code.
