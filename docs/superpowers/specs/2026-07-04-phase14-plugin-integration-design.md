> **Status:** Superseded by [`docs/architecture.md`](../../architecture.md) and [`docs/architecture/decisions/`](../../architecture/decisions/). This spec was a design document and is kept for historical reference only.

# Phase 14: Plugin System Integration — Design

**Status:** Design
**Date:** 2026-07-04

## Overview

Phase 13 created `PluginRegistry` (singleton) and `discover` (entry-point discovery)
but left them disconnected from the existing strategy/factor/workflow loading paths.
This phase wires them together so that:

- `polymind.strategies` uses `PluginRegistry` as its backing store
- `polymind.factors.registry` integrates with `PluginRegistry`
- `discover_all()` runs at CLI startup
- The CLI can list both built-in and discovered plugins

## Current State

```python
# strategies/__init__.py — module-level _registry dict, not connected to PluginRegistry
_registry: dict[str, type] = {}

# factors/registry.py — FactorRegistry, not connected to PluginRegistry
self._signals: dict[str, FactorSignalModel] = {}

# core/plugin.py — PluginRegistry singleton (unused by anything)
# core/discover.py — entry-point discovery (unused by anything)
```

## Target State

```
CLI startup / package import
        │
        ▼
PluginRegistry.reset()
        │
        ├── register_builtin_strategies()   ← strategies/__init__.py
        ├── register_builtin_factors()      ← factors/registry.py
        └── discover_all()                  ← core/discover.py
                │
                ▼
         PluginRegistry populated
                │
                ├── strategies CLI command reads PluginRegistry
                ├── factor engine reads PluginRegistry
                └── workflow engine reads PluginRegistry
```

## Module Changes

### `polymind/strategies/__init__.py`

- `register()` decorator → also calls `PluginRegistry().register_strategy()`
- `get_strategy()` → falls back to `PluginRegistry().get_strategy()` if name not in `_registry`
- `list_strategies()` → merges `_registry` with `PluginRegistry().list_strategies()`
- Add `register_builtin_strategies()` that registers all known built-in strategies

### `polymind/factors/registry.py`

- `FactorRegistry.register_signal()` → also calls `PluginRegistry().register_factor()`
- `FactorRegistry.list_signals()` → includes discovered plugins
- Add `register_builtin_factors()` that registers all known built-in factor signals

### `polymind/core/__init__.py`

- On import, run `register_builtin_strategies()` and `register_builtin_factors()`
- Optionally run `discover_all()` (with try/except for environments without plugins)

### `polymind/cli/main.py`

- `run` and `list` commands show registered + discovered plugins
- `polymind list --plugins` shows third-party plugins only

## Testing

- Unit tests verify that `register()` decorator populates both legacy and PluginRegistry
- Unit tests verify that `register_builtin*()` registers known strategies
- Integration test simulates discovery with mock entry points
- All existing 1017 tests remain passing
- No new external dependencies

## Backward Compatibility

- `get_strategy()` from `strategies/__init__.py` still works exactly as before
- `FactorRegistry` public API unchanged
- Existing tests need zero modification
