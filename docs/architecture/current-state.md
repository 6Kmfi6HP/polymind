# Current State

**Status:** Documentation truth source
**Date:** 2026-07-04 19:00

This file records repository state separately from the target architecture in
`../architecture.md`.

## Implemented

- **Phase 0: README status sections** — Added "Planned" (4 items) and "Research-Blocked"
  (3 items) sections to README.md after Current Status, before Quick Start. Uses
  consistent table formatting. ([2026-07-05] GAP-001)
- **Phase 0: THIRD_PARTY.md** — Created THIRD_PARTY.md at repo root documenting all
  8 external merged projects with source URL, license, derived files, and compatibility
  status. ([2026-07-05] GAP-002)
- **Phase 0: ADR 0005 LGPL Boundary** — ADR documenting LGPL isolation strategy (pip
  extras, adapter package, or subprocess boundary); confirms no LGPL code copied.
  ([2026-07-05] GAP-003)
- **Phase 0: Spec supersession markers** — All 27 docs/superpowers/specs/*.md files
  marked as superseded by architecture.md and decisions/. ([2026-07-05] GAP-004)
- **Phase 4: Official MM parity doc** — Comprehensive design divergence analysis in
  docs/references/official-mm-parity.md with 4 scenarios, formula comparison, and
  parity status matrix. ([2026-07-05] GAP-005)
- **Phase 5: Workflow paper_mode** — paper_mode flag added to all 4 workflow
  state machine constructors + WorkflowRunner wire-up. ([2026-07-05] GAP-007)
- **Phase 9: Release checklist** — RELEASE.md created with 4-step release
  process; Makefile check-release-readiness target. ([2026-07-05] GAP-014)
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
- **Phase 5: Workflow State Machine Docs** — 4 lightweight spec docs in
  docs/strategies/workflows/ (maker-rebate, event-mm, sniper, copy-trade). Each covers
  state transitions, error handling, recovery paths, and simulation/paper mode with
  mermaid diagrams and transition tables. ([2026-07-05] GAP-006)
	- **Phase 7: ResearchOutcome enum** — PASS, FAIL, NO_EDGE, INCONCLUSIVE added to
  factor_analysis.py; outcome field in FactorCard and FactorBacktestResult, computed
  from sharpe/drawdown thresholds. ([2026-07-05] GAP-010)
	- **Phase 7: ExecutionEvidence** — execution_model/slippage/fill_rate/cost fields
  separated from signal metrics in FactorCard and FactorBacktestResult, summary
  reports signal and exec evidence independently. ([2026-07-05] GAP-008)
- **Phase 8: Validation pipeline** — ValidationGate dataclass with 3 gates (schema,
  implementation status, risk limits) integrated into StrategyGenerator.generate();
  docs/studio/validation-gates.md documents the chain. ([2026-07-05] GAP-011)
- **Phase 9: CI pipeline additions** — 3 new CI jobs (license-provenance-check,
  adapter-conformance, factor-regression) added to .github/workflows/ci.yml.
  ([2026-07-05] GAP-013)
- **Phase 8: GeneratedConfig provenance** — 4 fields (provenance, source_version,
  risk_limits, execution_policy) added to GeneratedConfig, populated by all 7
  generation paths. ([2026-07-05] GAP-012)
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
- **Phase 7: Factor Promotion Gate** — FactorPromotionGate enforces all 7 evidence
  requirements before factor approval. Includes CapacityAnalysis, ExecutionSensitivityReport,
  FailureAnalysis dataclasses and PromotionCheckReport with pass/fail summary. 28 unit tests.
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
- **Phase 30: Strategy Templates Library** — 7 pre-configured templates (AMM, Bands,
  Classic MM, Maker Rebate, Event MM, Sniper, Momentum Factor), CLI integration.
- **Phase 31: DuckDB Research Panels** — SQL-queryable market price warehouse with
  3 tables (market_prices, market_metadata, factor_scores), summary analytics.
- **Phase 32: CLOB SDK Conformance** — adapter validation framework covering client,
  gateway, WebSocket, and signer interfaces.
- **Phase 33: Factor CLI** — `polymind factor discover` / `polymind factor backtest` commands.
- **Phase 34: Kalshi Adapter** — ExchangeAdapter implementation for Kalshi prediction markets.
- **Phase 35: LLM Factor Discovery** — Anthropic/OpenAI-powered factor definition parsing.
- **Phase 36: HTML Gallery** — self-contained static web gallery for strategy templates.

## Delivered in v0.4.x

- **Kalshi Adapter** — multi-venue support with Polymarket + Kalshi.
- **LLM-powered Factor Discovery** — Anthropic/OpenAI integration.
- **Strategy Templates Gallery** — static HTML page with all 7 templates.
- **Factor CLI** — `polymind factor discover` and `factor backtest` commands.

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
