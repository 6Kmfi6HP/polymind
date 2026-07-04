# Phase 14: Plugin System Integration — Implementation Plan

> **For agentic workers:** Implement per the design spec at `docs/superpowers/specs/2026-07-04-phase14-plugin-integration-design.md`.

**Goal:** Wire `PluginRegistry` into existing strategy/factor loading paths so that built-in and third-party plugins are discoverable from one unified registry.

**Tech Stack:** Python 3.10+, stdlib only

---

### Task 1: Wire PluginRegistry into strategies/__init__.py

**Files:**
- Edit: `polymind/strategies/__init__.py`
- Edit: `polymind/core/plugin.py` (export from core package)
- Test: `tests/strategies/test_strategies_registry.py` (new)

**Changes:**
1. `register()` decorator → also calls `PluginRegistry().register_strategy(name, cls)`
2. `get_strategy()` → merges `_registry` with `PluginRegistry().get_strategy()`
3. `list_strategies()` → merges both registries
4. Add `register_builtin_strategies()` that imports and registers all built-in strategies:
   - AMMStrategy, BandsStrategy, ClassicMMStrategy

---

### Task 2: Wire PluginRegistry into factors/registry.py

**Files:**
- Edit: `polymind/factors/registry.py`
- Test: `tests/factors/test_factor_registry_wiring.py` (new)

**Changes:**
1. `FactorRegistry.register_signal()` → also calls `PluginRegistry().register_factor()`
2. `FactorRegistry.list_signals()` → includes discovered plugins
3. Add `register_builtin_factors()` that registers known factor signal models

---

### Task 3: Wire PluginRegistry into core startup

**Files:**
- Edit: `polymind/core/__init__.py`
- Edit: `polymind/cli/main.py`

**Changes:**
1. On core import, run `register_builtin_strategies()` and `register_builtin_factors()`
2. CLI `list` command shows plugin count
3. `polymind list --plugins` filters to external plugins

---

### Task 4: Verify & commit

- Run full test suite (1017+ expected)
- Verify lint passes (ruff)
- Commit and push to `integration-tests` branch
