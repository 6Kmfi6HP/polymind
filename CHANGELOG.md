# Changelog

## [Unreleased]

### Infrastructure
- CHANGELOG.md created

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
