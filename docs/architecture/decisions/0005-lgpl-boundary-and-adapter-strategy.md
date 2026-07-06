# ADR 0005: LGPL Boundary and Adapter Strategy

**Status:** Accepted
**Date:** 2026-07-05

## Context

Polymind is MIT-licensed (`LICENSE`). The project references the
`evan-kolberg/prediction-market-backtesting` repository for backtesting concepts
such as passive order modeling, queue-position simulation, latency/partial-fill
realism, and multi-market reports.

That reference project builds on NautilusTrader, which is LGPL-licensed.
Specifically, `prediction-market-backtesting` contains NautilusTrader-adjacent
extension code and data-loading patterns that carry LGPL scoping concerns (see
`docs/architecture.md` lines 503-504). The polymind codebase must not
incorporate LGPL-covered source code directly into its MIT distribution.

## Decision

1. **No LGPL code has been copied into this repository.** Only MIT-licensed
   data-loading patterns and architecture ideas from the reference project were
   used. All code in `polymind/backtesting/` is original and MIT-licensed.

2. **Any future LGPL dependency MUST be isolated behind one of these strategies:**

   - **pip `extras` dependency** -- e.g., `pip install polymind[lgpl-backtesting]`
     with the LGPL package declared as an optional dependency in
     `pyproject.toml`. The LGPL component is never imported at the top level of
     the core package.

   - **Separate adapter package** -- A standalone Python package (e.g.,
     `polymind-nautilus-bridge`) that depends on `polymind` but not vice versa.
     The adapter package would carry the LGPL license and be distributed
     separately.

   - **Subprocess boundary** -- The LGPL-licensed component runs as a separate
     process, communicating with polymind over stdin/stdout, pipes, or a local
     socket. The parent process never links or imports the LGPL code.

3. **Before adding any LGPL dependency, the chosen isolation strategy MUST be
   documented** -- either as an update to this ADR or as a new ADR. A brief
   rationale for the strategy choice and a cross-reference to the upstream
   project's license file is required.

4. **`THIRD_PARTY.md` records the current status.** This file lives at the
   repository root and lists every external reference project, its license, and
   whether any of its source code is included (directly or adapted) in the
   polymind codebase. As of this ADR, all referenced projects are consulted for
   patterns only; no source code is copied.

## Consequences

- The core `polymind` package remains MIT-only, with no license-compliance risk
  from LGPL-scoped dependencies.
- Users who want NautilusTrader-backed backtesting must opt in explicitly via
  the chosen isolation mechanism (extra, adapter package, or subprocess).
- LGPL-scoped dependencies add maintenance cost: CI must test both with and
  without the optional dependency, and documentation must clarify the license
  boundary.
- The `THIRD_PARTY.md` file provides a single source of truth for license
  provenance, simplifying future audit.
- This strategy aligns with the Phase 0 documentation policy in
  `docs/architecture.md` (lines 370-376): "Third-party provenance and license
  boundaries are recorded before source is copied."
