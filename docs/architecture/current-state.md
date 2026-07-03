# Current State

**Status:** Documentation truth source
**Date:** 2026-07-03

This file records repository state separately from the target architecture in
`../architecture.md`.

## Implemented in the skeleton

- Python package scaffold under `polymind/`.
- CLI shell with help, status, setup, and strategy-list commands.
- Core package markers and base modules for agent, config, and strategy concepts.
- Placeholder package directories for strategies, factors, backtesting, storage,
  agents, alerts, studio, utilities, risk, and Polymarket adapters.
- Reference documentation for the cross-sectional momentum failure.
- **Phase 2 domain contracts (frozen):**
  - `PortfolioTarget` / `PositionDirection` — factor strategy portfolio output
  - `FillEvent` / `FillSource` — unified fill representation
  - `LedgerEntry` / `EntryType` — append-only P&L ledger entry
  - `RiskDecision` / `RiskGate` / `RiskContext` — composable risk gate contracts
  - `WorkflowCommand` / `CommandType` — workflow lifecycle and pair-management commands

## Not yet implemented

- Executable strategy backends for AMM, Bands, Maker Rebate, Event MM, Sniper,
  Copy Trade, Classic MM, or factor strategies.
- CLOB SDK v2/unified SDK adapter validation.
- Order manager, WebSocket adapters, Data API adapter, contracts gateway, signer,
  or reconciliation layer.
- Durable storage models, repositories, price snapshot store, or paper OMS ledger.
- Executable-price backtesting.
- Safety mechanisms: kill switch, preflight, log redaction, secure credential
  storage, live confirmation, and production risk enforcement.
- AI studio natural-language strategy generation.

## Documentation policy

- `README.md` must describe implemented work as implemented and planned work as
  planned.
- `docs/architecture.md` describes target architecture and roadmap gates.
- `docs/references/` stores evidence from source projects and must distinguish
  patterns to copy from anti-patterns to avoid.
- External specs are historical context; this repository records supersession here.

## Historical external spec

The historical spec at `../../../docs/superpowers/specs/2026-07-03-polymind-architecture-design.md`
belongs outside the `polymind` repository. It remains an initial draft for the
four-project market-making design. This repository's active architecture source
is `docs/architecture.md`.
