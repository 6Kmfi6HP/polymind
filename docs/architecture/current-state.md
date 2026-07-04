# Current State

**Status:** Documentation truth source
**Date:** 2026-07-04

This file records repository state separately from the target architecture in
`../architecture.md`.

## Implemented

- Python package scaffold under `polymind/`.
- CLI shell with help, status, setup, strategy-list, and report commands.
- Core packages: agent loop, config, domain contracts (Phase 2), strategy base,
  intents, fills, ledger, risk, portfolio, workflows, plugin registry, discovery.
- **Phase 2 domain contracts (frozen):**
  - `PortfolioTarget` / `PositionDirection` — factor strategy portfolio output
  - `FillEvent` / `FillSource` / `LedgerEntry` / `EntryType`
  - `RiskDecision` / `RiskGate` / `RiskContext`
  - `WorkflowCommand` / `CommandType`
  - `OrderIntent` / `CancelIntent` / `StrategyIntent`
- **Phase 4: AMM + Bands strategies** — pricing, sizing, full strategy modules.
- **Phase 5: All 7 strategies** — AMM, Bands, Classic MM, Maker Rebate, Event MM, Sniper,
  Copy Trade — each with config, analyze() producing StrategyIntent, full test coverage.
- **Phase 21: WorkflowRunner** — routes WorkflowCommand to state machines, type
  inference, PluginRegistry integration, lifecycle management (START/STOP/PAUSE/RESUME/
  RESTART), pair command delegation.
- **Phase 22: PairLifecycleManager** — YES/NO token pair lifecycle (split/merge/redeem/
  sell remainder/one-sided halt), inventory tracking, on-chain sync.
- **Phase 24: SnapshotCollector** — CLOB data collector, polls PolymarketDataAPI,
  stores in PriceStore, configurable poll interval and market limit.
- **Phase 25: TradingEngine** — central orchestrator wiring strategy→risk→executor,
  run_tick/run_forever, background task support.
- **Phase 26: Integration Test Suite** — full pipeline, workflow, risk, multi-strategy
  end-to-end tests. 69 integration tests.
- **Phase 5: Workflow state machines** — Maker Rebate, Event MM, Sniper, Copy Trade,
  each with full state machine, transitions, and unit tests.
- **Phase 21: WorkflowRunner** — routes WorkflowCommand to state machines, type
  inference, PluginRegistry integration, lifecycle management (START/STOP/PAUSE/RESUME/
  RESTART).
- **Phase 6: Factor framework** — pipeline, scoring, portfolio construction, filters,
  execution model, registry with built-in factors (momentum, volatility, sentiment,
  fair-value, composite, hedge, volume).
- **Phase 7: Factor strategies** — separate packages for each factor type, all
  implementing the score interface.
- **Phase 3: Execution** — PaperExecutor, FillModel, OrderIdentity, LiveExecutor,
  Serializer.
- **Phase 8: Studio** — NL-to-config generator, optimizer.
- **Phase 9: Reports** — Dashboard, positions, P&L, risk reports with Rich tables.
- **Phase 9: Docs** — Mkdocs site with strict build, mkdocs-material theme.
- **Phase 10: Operations dashboard** — CLI commands for dashboard/positions/pnl/risk.
- **Phase 12-13: Agent providers** — Anthropic, OpenAI, Gemini, Ensemble, Intelligence.
- **Phase 14: Plugin system** — PluginRegistry with entry-point discovery.
- **Phase 15-20: Polymarket adapters** — CLOB client, WebSocket, Data API, contracts
  gateway (split/merge/redeem), signer, errors, metrics, types (unified), LiveExecutor.
- **Reconciliation** — fill reconciliation, balance checks, recovery.
- **Storage** — database, warehouse, ledger, price store, models.
- **Safety** — KillSwitch, Preflight checks, secrets handling, logging.
- **CI** — GitHub Actions with tests + docs build on Python 3.11, pre-commit hooks (ruff).
- **Reference documentation** — cross-sectional momentum analysis, factor research,
  official MM keeper, terminal, probablyprofit, warproxxx patterns and anti-patterns.
- **Template project files** — Makefile, MANIFEST.in, .pre-commit-config.yaml,
  pyproject.toml with PyPI metadata, entry points.

## Not yet implemented

- CLOB SDK v2/unified SDK adapter conformance validation.
- Native DuckDB research panels (JSONL price store works; DuckDB is a future optimization).
- AI factor discovery (studio enhancement — NL→config exists, auto-factor discovery is next).
- Strategy templates gallery (10+ Enum templates exist; web gallery is future).
- Kalshi, Limitless, other venue adapters (multi-venue is Phase 9+ extension).

## Delivered in v0.2.x (no longer on the not-yet list)

- **OrderManager** — centralized order lifecycle tracking (Phase 28).
- **Executable-price backtesting** — FactorBacktester uses CLOB bid/ask, not mid-price (Phase 27).
- **Strategy backends** — all 7 strategies (AMM, Bands, Classic MM, Maker Rebate, Event MM,
  Sniper, Copy Trade) with real analyze() → StrategyIntent pipeline.
- **WorkflowRunner** — state machine command routing engine.
- **PairLifecycleManager** — YES/NO pair lifecycle (split/merge/redeem).
- **TradingEngine** — strategy → risk → executor orchestration.
- **CLOB SnapshotCollector** — live CLOB data ingestion pipeline.
- **Integration Test Suite** — 69+ end-to-end tests covering full pipeline.

## Documentation policy

- `README.md` must describe implemented work as implemented and planned work as
  planned.
- `docs/architecture.md` describes target architecture and roadmap gates.
- `docs/references/` stores evidence from source projects and must distinguish
  patterns to copy from anti-patterns to avoid.
- External specs are historical context; this repository records supersession here.

## Historical external spec

The historical spec at `../../../docs/superpowers/specs/2026-07-03-polymind-architecture-design.md`
belongs outside the `polymind` repository. This repository's active architecture source
is `docs/architecture.md`.
