# ADR 0003: On-chain balance is reconciliation truth

**Status:** Accepted
**Date:** 2026-07-03

## Context

The pm-terminal reference uses WebSocket and polling signals for fill detection,
but treats on-chain ERC-1155 balances as the source of truth when recovering
from ghost fills, partial fills, and lagging events.

Polymarket WebSocket documentation distinguishes public market streams from
authenticated user streams. These streams are necessary for low-latency wake-up
signals, but they are not a complete recovery model by themselves.

## Decision

WebSocket events are wake-up signals. CLOB and Data API reads are cross-checks.
On-chain balances are the reconciliation source for fills, merges, redemptions,
and final position truth where the workflow depends on token ownership.

## Consequences

- Live workflows must include reconciliation steps before irreversible actions.
- Paper OMS and storage must persist enough state to compare expected positions
  with observed user-channel events and on-chain balances.
- Strategy promotion requires recovery behavior, not only happy-path fills.
