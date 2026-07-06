# Architecture Conformance State

> 持续审查 `README.md`、`docs/architecture.md`、`docs/architecture/current-state.md`、`docs/architecture/roadmap-triage-state.md` 与仓库代码/测试/CI 的一致性。

## Loop Info
- Last run: 2026-07-06
- Pattern: architecture-conformance-loop
- Active item: ARCH-001
- Attempt: 1/3

## Scope
- `README.md`
- `docs/architecture.md`
- `docs/architecture/current-state.md`
- `docs/architecture/roadmap-triage-state.md`
- `mkdocs.yml`
- `polymind/`
- `tests/`
- `.github/workflows/ci.yml`

## Backlog

| ID | Area | Type | Priority | Status | Next action |
|---|---|---|---|---|---|
| ARCH-001 | README Planned vs implemented | doc drift | high | done | Verified: all 4 README Planned items fully implemented (THIRD_PARTY.md, ADR 0005, superseded markers; parity suite+doc; paper_mode in all workflows; RELEASE.md + Makefile target). Merged into Current Status table, removed Planned section. |
| ARCH-002 | current-state completeness | doc drift | high | pending | Audit newly added reference-port work and missing implementation entries |
| ARCH-003 | roadmap-triage freshness | conformance audit | medium | pending | Re-check "all gaps resolved" against current code/tests/CI evidence |
| ARCH-004 | architecture target vs package layout | conformance audit | medium | pending | Compare `docs/architecture.md` target layout with actual package tree |
| ARCH-005 | workflow docs vs state machines | conformance audit | medium | pending | Verify workflow docs still match implementation and paper_mode behavior |

Status: `pending` | `in_progress` | `partial` | `done` | `blocked`

## Active Work Item
- ID: ARCH-001 (Resolved)
- Area: README Planned vs implemented
- Outcome: All 4 "Planned" items verified implemented and moved to Current Status table

## Findings
- ARCH-001: README listed 4 "Planned" items that are fully implemented — License & Provenance (THIRD_PARTY.md, ADR 0005, superseded markers), Official MM Parity (35-test suite + divergence analysis), Workflow Simulation Mode (paper_mode in all 4 state machines + runner), Release & Packaging (RELEASE.md + Makefile check-release-readiness). Fixed: moved to ✅ Complete table.
- Also corrected test count: 1,715 → 1,924 (actual `pytest --collect-only` result).

## Human Inbox
- Empty.

## Run History
| Timestamp | Item | Outcome | Notes |
|-----------|------|---------|-------|
| 2026-07-06 | ARCH-001 | Fixed | 4 Planned items moved to Complete; test count 1,715→1,924 |
