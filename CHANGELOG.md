# Changelog

## [v0.7.0] — 2026-07-05

### Added
- Factor features module (`polymind/factors/features.py`) — micro-price, weighted mid, depth imbalance, momentum/volatility from history, FeatureComputer with per-market price history tracking (37→45 tests, 100% coverage)
- Standalone scripts: `scripts/collect_snapshots.py` (CLOB data collection daemon) and `scripts/backtest_factor.py` (factor backtest runner with text/JSON output)
- Monitoring module (`polymind/monitoring/metrics.py`) — MetricsCollector + MetricsSnapshot for tracking orders, fills, cancellations, errors, P&L, and latency (22 tests)
- MyPy configuration (pyproject.toml) — suppresses third-party stub errors, project-wide mypy now at 0 errors

### Fixed
- 39 mypy type errors across 11 files → 0 errors
- `classic_mm/__init__.py` — export ClassicMMStrategy for broken entry point
- `web/__init__.py` — create missing package init
- `mkdocs.yml` — fix incomplete repo_url
- `docs/index.md` — outdated "Phase 0/1" status

## [v0.6.0] — 2026-07-05

### Added
- Limitless exchange adapter (Phase 37) — implements ExchangeAdapter ABC
- Advanced factor analysis (Phase 38) — IC, decay, walk-forward
- IC analytics integrated into FactorCard + CLI display (Phase 39-40)
- `factor recommend` command — tests 6 variations, reports best (Phase 41)
- `polymind daemon` command — continuous TradingEngine loop (Phase 43)
- `polymind plugin` CLI — plugin ecosystem management (Phase 44)
- README updated with current stats: 1648 tests, 98% coverage

### Changed
- CLI coverage 90% → 92%
- FactorBacktestConfig → FactorAnalyzer integration improves IC computation

## [v0.5.0] — 2026-07-04

### Added
- CLI coverage 41% → 90% with 25 CliRunner integration tests
- Factor Discovery 100% coverage (Anthropic/OpenAI mock tests)
- DuckDB PriceStore backend — `backend="duckdb"` flag on PriceStore
- Overall test suite: 1555 tests, 98% coverage
- All remaining coverage gaps closed: agent.py, config.py, fill_model.py → 100%

## [v0.4.0] — 2026-07-03

### Added
- Kalshi exchange adapter (Phase 34)
- LLM factor discovery (Anthropic/OpenAI, Phase 35)
- HTML gallery generator (Phase 36)
- DuckDB research panels (Phase 31)
- CLOB SDK conformance validation (Phase 32)
- Factor CLI commands (Phase 33)

## [v0.3.0] — 2026-07-02

### Added
- AI Factor Discovery Engine (Phase 29)
- Strategy Templates Library (Phase 30)
- WorkflowRunner, TradingEngine, PairLifecycleManager (Phases 21-28)
- Plugin wiring, adapter layer, LiveExecutor, type unification (Phases 14-20)

## [v0.2.0] — 2026-07-01

### Added
- All 7 strategies
- Workflow state machines (4 types)
- 69 integration tests
- Factor framework

## [v0.1.0] — 2026-06-30

### Added
- Python package scaffold
- CLI, core packages, domain contracts
- TDD test suite, CI, pre-commit hooks
