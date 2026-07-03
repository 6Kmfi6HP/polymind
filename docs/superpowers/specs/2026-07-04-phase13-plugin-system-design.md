# Phase 13: Plugin System — Design

**Status:** Design
**Date:** 2026-07-04

## Overview

Add a plugin system that allows third-party strategies, factors, and workflows to be pip-installed and registered as Polymind extensions. Per Phase 9 roadmap: "Plugin system and multi-platform research are explicit extensions."

## Architecture

```
polymind/
└── core/
    ├── plugin.py        # Plugin base class & registry (new)
    └── discover.py      # Plugin discovery via entry points (new)
```

### Plugin Types

- **StrategyPlugin** — Custom market-making strategies
- **FactorPlugin** — Custom factor signals
- **WorkflowPlugin** — Custom workflow state machines

### Registration

Plugins register via `pyproject.toml` entry points:

```toml
[project.entry-points."polymind.strategies"]
my_strategy = "mypackage:MyStrategy"

[project.entry-points."polymind.factors"]
my_factor = "mypackage:MyFactor"
```

### Discovery

`polymind.core.discover`:
```python
def discover_strategies() -> dict[str, type]:
    """Find all installed strategy plugins via entry points."""
```

`polymind.core.plugin`:
```python
class PluginRegistry:
    """Global registry for all plugin types."""

    def register_strategy(self, name, cls): ...
    def discover_all(self): ...
    def get_strategy(self, name): ...
```

## Testing

- Unit tests with mock entry points
- Test registration and discovery without real packages
