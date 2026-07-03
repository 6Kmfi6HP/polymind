# ADR 0002: Strategies emit intents; executors place orders

**Status:** Accepted
**Date:** 2026-07-03

## Context

The official market-maker reference separates strategy math from order mutation:
strategies compute expected orders from snapshots, while the order manager
places and cancels orders.

Other references show the cost of mixing responsibilities: monolithic trading
files, WebSocket callbacks that mutate strategy state, and services that combine
policy, transport, persistence, and wallet side effects.

## Decision

Strategies produce order intents, expected-order deltas, or workflow commands.
Executors own CLOB transport, retries, cancellations, order state mutation, and
exchange-specific errors.

Wallet and chain adapters own split, merge, redeem, approvals, and on-chain
balance reads.

## Consequences

- Strategy modules remain testable from immutable snapshots.
- Live transport can be swapped or upgraded without rewriting strategy policy.
- Risk gates can inspect intents before execution.
- Workflow-specific state machines can coordinate execution without embedding
  SDK or wallet calls in strategy code.
