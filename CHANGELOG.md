# Changelog

All notable changes to Polymind will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.1.0] - 2026-07-04

### Added

- **Architecture-complete implementation**: All 61 modules across 15 layers implemented
  - Core: agent, config, intents, strategy, fills, ledger, portfolio, risk, workflows
  - Execution: executor, order_identity, fill_model, serializer
  - Strategies: AMM (pricing/sizing/strategy), Bands (pricing/sizing/strategy), Classic MM
  - Workflows: MakerRebate, EventMM, Sniper, CopyTrade state machines
  - Polymarket adapters: client, websocket, data_api, contracts, signer, metrics
  - Reconciliation: fills, balances, recovery
  - Storage: price_store, database, models, ledger, warehouse
  - Risk: manager, limits, drawdown, exposure
  - Backtesting: engine, data, metrics, execution_model, factor_bt
  - Factors: pipeline, registry, filters, execution, portfolio_construction
  - Studio: generator, optimizer
  - Agents: base agent ABC (anthropic, openai, gemini, ensemble)
  - Alerts: telegram
  - Utils: logging, secrets, killswitch, preflight
  - CLI: main (click-based)

- **Integration test suite**: Paper trading end-to-end, factor pipeline integration,
  safety and reconciliation integration tests

- **Documentation site**: mkdocs-based documentation with API reference, architecture
  guide, and strategy examples gallery

- **CI pipeline**: GitHub Actions with ruff lint, pytest, bandit security scan,
  and coverage reporting

- **Strategy templates**: AMM ladder, Factor bridge, Safety templates gallery

- **Operator dashboard**: CLI-based reporting system (`polymind report`)
  - Position summary with P&L breakdown
  - Per-market P&L with total and cash balance
  - Risk status with drawdown and limits monitoring
  - Combined dashboard view

- **Developer tooling**:
  - Makefile with test, lint, format, build, clean targets
  - Pre-commit hooks (ruff, trailing-whitespace, end-of-file-fixer, YAML/JSON/TOML checks)
  - Proper PyPI packaging metadata

### Changed

- Separated target architecture (`docs/architecture.md`) from current implementation state
- Applied consistent formatting and style across 123 source files

### Fixed

- License expression compliance with PEP 639
- Event loop management in CLI commands (extracted `_run_async` helper)
- Various ruff lint issues (unused variables, ambiguous names, `isinstance` syntax)

### Architecture

```
polymind/           # Main package (61 modules, 15 layers)
tests/              # 831 tests across all modules
docs/               # Architecture docs, specs, plans, strategy templates
.github/workflows/  # CI pipeline (ruff + pytest + bandit)
```

### Test Statistics

- **Total tests**: 831
- **Integration tests**: 3 suites (paper trading, factor pipeline, safety reconciliation)
- **Strategy tests**: AMM, Bands, Classic MM, factor strategies
- **Workflow tests**: MakerRebate, EventMM, Sniper, CopyTrade
- **Adapter tests**: Polymarket client, WebSocket, Data API, contracts, signer, metrics
- **Coverage target**: 70% minimum

---

## [0.1.0-rc.1] - 2026-07-03

- Initial release candidate with all Phase 0–9 architecture modules
- 760+ tests, CLI interface, AI strategy generation
