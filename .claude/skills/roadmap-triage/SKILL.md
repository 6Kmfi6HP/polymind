---
name: roadmap-triage
description: >
  Triage roadmap requirements against repository evidence and write a structured
  state report.
user_invocable: true
---

# Roadmap Triage

Compare `docs/architecture.md` requirements with repository evidence and write the results to `docs/architecture/roadmap-triage-state.md`.

## Inputs
- `docs/architecture.md`
- `docs/architecture/current-state.md`
- `docs/architecture/roadmap-triage-state.md`
- `docs/architecture/loop-run-log.md`
- Repository code, tests, docs, and CI files

## L1 Report-Only Rule
- L1 is report-only.
- NEVER modify application code.
- NEVER modify tests, runtime config, dependencies, migrations, or secrets.
- L1 may update only `docs/architecture/roadmap-triage-state.md` and `docs/architecture/loop-run-log.md`.

## Flow
1. Read `docs/architecture.md` and extract the Phase 0-9 requirements.
2. Read `docs/architecture/current-state.md` and the existing triage state.
3. Search the repository for direct evidence in code, tests, docs, CLI commands, and CI configuration.
4. Classify each requirement as `Done`, `Partial`, `Missing`, or `Blocked`.
5. Convert every `Partial`, `Missing`, or `Blocked` requirement into a gap record.
6. Update `docs/architecture/roadmap-triage-state.md`:
   - refresh `Loop Info`
   - refresh `Phase Status Overview`
   - replace `Gaps Found`
   - add escalation items to `Human Inbox`
   - keep `Run History` to the last 10 lines
7. Append one line to `docs/architecture/loop-run-log.md` using the required log format.

## Evidence Rules
- Ground every status in repository evidence.
- Quote the requirement text verbatim in each gap.
- Prefer code, tests, docs, and CI over inference.
- If evidence is missing, say so.
- Do not guess.
- One gap per unmet requirement.

## Output Format
Use this format for requirement summaries and intermediate reports:

`Phase | Requirement | Status | Evidence`

## Gap Record Format
- ID: `GAP-NNN`
- Severity: `low | medium | high`
- Phase: `Phase N`
- Requirement: `<verbatim requirement text>`
- Current state: `<observed evidence or absence>`
- Suggested action: `<smallest next step>`
- Attempts: `<number>`
- Escalated: `Yes | No`

## L1 Boundaries
- NEVER change application behavior.
- NEVER edit files outside the two triage documents.
- NEVER create fake gaps or fake evidence.
- If a requirement would require a code or config change, stop at report-only and send it to `Human Inbox`.
