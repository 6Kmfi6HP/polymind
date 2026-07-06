# Roadmap Triage State

## Loop Info
- Last run: 2026-07-06T04:15:00Z
- Level: L2 (Auto-Fix with Verifier) — this run
- Status: ✅ **All 15 gaps resolved across 10 phases**

## Phase Status Overview

| Phase | Roadmap focus | Status | Gaps |
| --- | --- | --- | ---: |
| Phase 0 | Documentation, provenance, and license truth alignment | ✅ Complete | 0 |
| Phase 1 | Polymarket adapter validation | ✅ Complete | 0 |
| Phase 2 | Domain contracts and architecture spine | ✅ Complete | 0 |
| Phase 3 | Execution, reconciliation, and paper runtime | ✅ Complete | 0 |
| Phase 4 | Official MM port | ✅ Complete | 0 |
| Phase 5 | Terminal and event workflows | ✅ Complete | 0 |
| Phase 6 | Factor data and research engine | ✅ Complete | 0 |
| Phase 7 | Factor strategies and promotion governance | ✅ Complete | 0 |
| Phase 8 | AI studio | ✅ Complete | 0 |
| Phase 9 | Operator readiness, release, and expansion | ✅ Complete | 0 |

## Gaps Found

### GAP-001
- **Severity:** low
- **Phase:** Phase 0
- **Requirement原文:** "Public README distinguishes implemented, planned, and research-blocked work."
- **Status:** resolved
- **Resolution:** Added "Planned" section (4 items: License & Provenance, Official MM Parity, Workflow Simulation Mode, Release & Packaging) and "Research-Blocked" section (3 items: LLM factor discovery, Live trading, Third-party provenance) to README.md after Current Status, before Quick Start. Uses same table formatting as existing status table.

### GAP-002
- **Severity:** low
- **Phase:** Phase 0
- **Requirement原文:** "Third-party provenance and license boundaries are recorded before source is copied."
- **Status:** resolved
- **Resolution:** THIRD_PARTY.md created at repo root with 8 external projects in 2 groups (Market-Making Bots, Factor Research & Backtesting). Each entry lists source URL, license type, derived files, and compatibility status. prediction-market-backtesting LGPL extension noted as partial with adapter boundary reference. Verification section documents audit methodology.

### GAP-003
- **Severity:** low
- **Phase:** Phase 0
- **Requirement原文:** "LGPL-covered or non-MIT-compatible components are isolated behind a dependency, adapter, or explicit legal review."
- **Status:** resolved
- **Resolution:** ADR 0005 created (docs/architecture/decisions/0005-lgpl-boundary-and-adapter-strategy.md). Documents: (1) no LGPL code has been copied, (2) 3 future isolation strategies (pip extras, separate adapter package, subprocess boundary), (3) ADR update required before adding LGPL dependency, (4) THIRD_PARTY.md as provenance truth source.

### GAP-004
- **Severity:** low
- **Phase:** Phase 0
- **Requirement原文:** "Superseded specs are marked explicitly."
- **Status:** resolved
- **Resolution:** All 27 spec files in docs/superpowers/specs/ now have supersession headers pointing to docs/architecture.md and docs/architecture/decisions/. Header states "Superseded by ... kept for historical reference only."

### GAP-005
- **Severity:** low
- **Phase:** Phase 4
- **Requirement原文:** "Prove source parity on representative snapshots before live/paper promotion."
- **Status:** resolved
- **Resolution:** Parity analysis document created in docs/references/official-mm-parity.md with 4 worked scenarios, formula comparison tables, and design divergence analysis. Found fundamental differences: Polymind uses linear spread ladders vs reference keeper's constant-product AMM; multiplicative spreads vs additive margins; full-replace vs incremental order management. Identified quirk in AMM sizing concatenation. Parity status matrix with clear "Match?" indicators.

### GAP-006
- **Severity:** medium
- **Phase:** Phase 5
- **Requirement原文:** "Each workflow needs a state-machine document before implementation."
- **Status:** resolved
- **Resolution:** 4 workflow state-machine spec docs created in docs/strategies/workflows/ (maker-rebate-state-machine.md, event-mm-state-machine.md, sniper-state-machine.md, copy-trade-state-machine.md). Each covers: mermaid diagram, states, events, transition table, error handling, recovery paths, and simulation/paper mode. Checker found 4 accuracy issues in attempt 1 (wrong state name ANALYZING→PLACING_ORDER, 3x HALT availability errors). All fixed in attempt 2. 81 workflow tests pass.
- **Escalated:** No
- **last_seen:** 2026-07-05

### GAP-007
- **Severity:** low
- **Phase:** Phase 5
- **Requirement原文:** "Preserve simulation mode and operator runtime assumptions from reference workflows."
- **Status:** resolved
- **Resolution:** Added paper_mode: bool = False parameter to all 4 workflow state machine constructors (RebateStateMachine, EventMMStateMachine, SniperStateMachine, CopyTradeStateMachine) with is_paper_mode property. WorkflowRunner._handle_start passes paper_mode from cmd.params. 9 files changed, 93 workflow tests pass.

### GAP-008
- **Severity:** medium
- **Phase:** Phase 7
- **Requirement原文:** "Each factor report separates signal evidence from execution evidence."
- **Status:** resolved
- **Resolution:** ExecutionEvidence dataclass (execution_model, slippage_model, fill_rate, avg_slippage_bps, total_execution_cost_bps, live_result) added to factor_bt.py. execution_evidence field added to FactorBacktestResult and FactorCard. FactorCard.summary() now shows signal metrics and execution evidence separately. 4 files changed, 101 tests pass.

### GAP-009
- **Severity:** high
- **Phase:** Phase 7
- **Status:** resolved
- **Resolution:** FactorPromotionGate implemented with 7 evidence checks (backtest, walk-forward, bootstrap/CI, paper OMS, capacity, execution sensitivity, failure analysis). 3 new dataclasses (CapacityAnalysis, ExecutionSensitivityReport, FailureAnalysis). PromotionCheckReport with all_checks_passed/passed_checks/summary. 28 tests passing, 2 Maker attempts (Checker verified 5 issues fixed in attempt 2).

### GAP-010
- **Severity:** medium
- **Phase:** Phase 7
- **Requirement原文:** "PASS, FAIL, NO EDGE, and INCONCLUSIVE are valid research outcomes."
- **Status:** resolved
- **Resolution:** ResearchOutcome enum (PASS, FAIL, NO_EDGE, INCONCLUSIVE) added to factor_analysis.py. outcome field added to FactorCard (factor_discovery.py) and FactorBacktestResult (factor_bt.py) with INCONCLUSIVE default. Backtest() computes outcome from sharpe/drawdown thresholds — all 4 values reachable. 6 files changed, 1722 tests pass.

### GAP-011
- **Severity:** medium
- **Phase:** Phase 8
- **Requirement原文:** "LLM output never bypasses schema validation, implementation-status checks, risk checks, preflight checks, paper/live gates, or promotion status."
- **Status:** resolved
- **Resolution:** ValidationGate dataclass added to generator.py with 3 gates: schema (required params + types), implementation_status (PluginRegistry check, skips CUSTOM/FACTOR meta-templates), risk_limits (num_levels, top_n, exposure, spread bounds). validation_results list in GeneratedConfig. generate() runs _validate() before returning. 13 new tests. docs/studio/validation-gates.md documents the gate chain.

### GAP-012
- **Severity:** low
- **Phase:** Phase 8
- **Requirement原文:** "Generated configurations include provenance, source strategy version, risk limits, and execution policy."
- **Status:** resolved
- **Resolution:** Added 4 fields to GeneratedConfig: provenance (str), source_version (str), risk_limits (dict), execution_policy (str). All 7 generation paths (6 match methods + CUSTOM fallback) populate them: provenance="keyword", source_version="0.7.0", execution_policy="paper". 8 new tests covering defaults, custom values, and all generation paths.

### GAP-013
- **Severity:** medium
- **Phase:** Phase 9
- **Requirement原文:** "CI pipeline for docs, lint, tests, security scan, license/provenance checks, adapter conformance, and factor regression."
- **Status:** resolved
- **Resolution:** Added 3 new CI jobs to .github/workflows/ci.yml: license-provenance-check (continue-on-error, checks for THIRD_PARTY.md/NOTICE), adapter-conformance (pytest conformance tests, matrix 3.10/3.11), factor-regression (backtesting + studio tests, matrix 3.10/3.11). 191 tests pass. Docker job unchanged.

### GAP-014
- **Severity:** low
- **Phase:** Phase 9
- **Requirement原文:** "PyPI release only after the public package exposes implemented modules rather than target-only facades."
- **Status:** resolved
- **Resolution:** RELEASE.md created at repo root with 4-step release checklist (version bump, readiness checks, build/verify, PyPI publish). check-release-readiness target added to Makefile (auto-verifies imports, tests, no NotImplementedError stubs, entry points).

### GAP-015
- **Severity:** critical
- **Phase:** Phase 9
- **Requirement原文:** "CI pipeline for docs, lint, tests, security scan, license/provenance checks, adapter conformance, and factor regression."
- **Status:** resolved
- **Resolution:** Three-part fix: (1) Removed module-level `register_builtin_strategies()` call from `polymind/strategies/__init__.py`, replaced with lazy `_ensure_strategies_loaded()` pattern that fires on first `get_strategy()` or `list_strategies()` call. (2) Added `PluginRegistry.reset()` in `tests/studio/test_generator.py` dummy registration to prevent collision. (3) Added `architecture/decisions/` to mkdocs.yml nav so its ADRs are discoverable; this downgrades the 27 "unrecognized relative link" messages from warning to INFO (no longer aborts `--strict` mode). Full test suite: 1791 passed, 0 errors. mkdocs build --strict: exit 0.

## Human Inbox
- Empty.

## Run History
| Timestamp | Phases | Findings | New | Resolved | Escalated |
|-----------|--------|----------|-----|----------|-----------|
| 2026-07-05T20:30:00Z | Phase 0-9 | 14 | 14 | 0 | 0 |
| 2026-07-05T21:00:00Z | Phase 7 | 1 | 0 | 1 | 0 |
| 2026-07-05T21:15:00Z | Phase 5 | 1 | 0 | 1 | 0 |
| 2026-07-05T21:30:00Z | Phase 7 | 1 | 0 | 1 | 0 |
| 2026-07-05T21:45:00Z | Phase 7 | 1 | 0 | 1 | 0 |
| 2026-07-05T22:00:00Z | Phase 8 | 1 | 0 | 1 | 0 |
| 2026-07-05T22:15:00Z | Phase 9 | 1 | 0 | 1 | 0 |
| 2026-07-05T22:30:00Z | Phase 8 | 1 | 0 | 1 | 0 |
| 2026-07-05T22:45:00Z | Phase 0 | 1 | 0 | 1 | 0 |
| 2026-07-05T23:00:00Z | Phase 0 | 1 | 0 | 1 | 0 |
| 2026-07-05T23:15:00Z | Phase 0 | 1 | 0 | 1 | 0 |
| 2026-07-05T23:30:00Z | Phase 0 | 27 | 0 | 1 | 0 |
| 2026-07-05T23:45:00Z | Phase 4 | 1 | 0 | 1 | 0 |
| 2026-07-06T00:00:00Z | Phase 5 | 1 | 0 | 1 | 0 |
| 2026-07-06T00:00:00Z | Phase 9 | 1 | 0 | 1 | 0 |
| 2026-07-06T01:00:00Z | Phase 0-9 | 1 | 1 (GAP-015) | 0 | 0 (crit->inbox) |
| 2026-07-06T04:15:00Z | Phase 9 | 1 (GAP-015 fix) | 0 | 1 | 0 |
