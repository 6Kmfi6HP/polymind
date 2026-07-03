# Phase 13: Plugin System — Implementation Plan

> **For agentic workers:** Use superpowers:executing-plans or implement manually.

**Goal:** Add plugin discovery and registration system for third-party strategies, factors, and workflows.

**Architecture:** Two new core modules: `plugin.py` (registry) and `discover.py` (entry point discovery).

**Tech Stack:** Python 3.10+, `importlib.metadata` (stdlib)

---

### Task 1: Plugin Registry

**Files:**
- Create: `polymind/core/plugin.py`
- Test: `tests/core/test_plugin.py`

Implement `PluginRegistry` singleton:
- `register_strategy(name, cls)`, `register_factor(name, cls)`, `register_workflow(name, cls)`
- `get_strategy(name)`, `get_factor(name)`, `get_workflow(name)`
- `list_strategies()`, `list_factors()`, `list_workflows()`
- Error on duplicate registration

---

### Task 2: Plugin Discovery

**Files:**
- Create: `polymind/core/discover.py`
- Test: `tests/core/test_discover.py`

Implement entry point discovery:
- `discover_strategies() -> dict[str, type]`
- `discover_factors() -> dict[str, type]`
- `discover_workflows() -> dict[str, type]`
- Uses `importlib.metadata.entry_points()` with group prefixes
- Returns empty dict when no plugins installed

---

### Task 3: Integration & Verification

- Wire registry into existing strategy/workflow loading paths
- Run full test suite (916+ expected)
- Commit and push
