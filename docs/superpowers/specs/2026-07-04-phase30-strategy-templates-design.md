# Phase 30: Strategy Templates Library — Design

**Status:** Design
**Date:** 2026-07-04

## Overview

A library of pre-configured, production-ready strategy templates that users
can deploy with a single command. Each template bundles a strategy type with
sensible defaults, documentation, and risk limits.

## Architecture

```
polymind/templates/
├── __init__.py
├── library.py          # TemplateLibrary — registry of all templates
├── base.py             # StrategyTemplate base class
├── amm_concentrated.py   # AMM concentrated liquidity template
├── bands_multi.py        # Bands multi-level template
├── maker_rebate_pair.py  # Maker Rebate YES/NO pair template
├── event_mm_trigger.py   # Event-driven MM template
├── sniper_discount.py    # Deep discount sniper template
├── momentum_factor.py    # Cross-sectional momentum factor template
```

### TemplateLibrary

```python
class TemplateLibrary:
    def list_templates() -> list[TemplateInfo]
    def get_template(name) -> TemplateInfo
    def instantiate(name, overrides=None) -> StrategyConfig
```

### Each template provides
- Pre-configured parameters
- Risk limits
- Description and use case
- CLI command for deployment

## CLI Integration

```bash
polymind templates                  # List all available templates
polymind template show <name>       # Show template details
polymind template run <name>        # Deploy a template
```
