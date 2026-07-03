# Phase 11: PyPI Release Readiness Design

**Status:** Design
**Date:** 2026-07-04

## Overview

Prepare the Polymind package for PyPI publication. This involves verifying the packaging configuration, ensuring the build is reproducible, adding a proper Makefile for developer tasks, and adding pre-commit hooks for code quality automation.

Per Phase 9 of the architecture roadmap: "PyPI release only after the public package exposes implemented modules rather than target-only facades" — all 61 modules are implemented, so this gate is cleared.

## Scope

1. **Makefile** — Common developer commands: test, lint, format, build, clean
2. **Pre-commit hooks** — `.pre-commit-config.yaml` with ruff, trailing whitespace, end-of-file-fixer, check-yaml, check-json
3. **pyproject.toml verification** — Ensure all required fields for PyPI are present
4. **Build verification** — `python -m build` works and produces a valid wheel
5. **CLI entry point** — Ensure the `polymind` console script is properly registered

## Files

| Action | File | Purpose |
|--------|------|---------|
| Create | `Makefile` | Developer task automation |
| Create | `.pre-commit-config.yaml` | Pre-commit hook configuration |
| Modify | `pyproject.toml` | Add missing PyPI metadata |
| Create | `MANIFEST.in` | Include necessary files in sdist |

## Success Criteria

- `make test` runs full test suite
- `make lint` runs ruff check
- `make build` produces a valid wheel + sdist
- `make clean` removes build artifacts
- `pre-commit run --all-files` passes
- `pip install dist/*.whl` installs successfully
