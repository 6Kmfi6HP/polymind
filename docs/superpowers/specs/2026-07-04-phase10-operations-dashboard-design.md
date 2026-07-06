> **Status:** Superseded by [`docs/architecture.md`](../../architecture.md) and [`docs/architecture/decisions/`](../../architecture/decisions/). This spec was a design document and is kept for historical reference only.

# Phase 10: Operations Dashboard Design

**Status:** Approved Design
**Date:** 2026-07-04

## Overview

Operator Dashboard 是 Phase 9 "Operator readiness" 的延续。提供 CLI 驱动的报告系统，汇总 fills、positions、P&L 和风险状态，为运营者提供一键式状态概览。

## Architecture

```
CLI (click/rich) → reports/ modules → storage/ledger + risk/manager
```

报告模块从现有存储层读取数据（LedgerStore、RiskManager），输出 Rich 格式化的控制台表格。

## Components

### 1. `polymind/reports/` Package

| Module | Responsibility |
|--------|---------------|
| `__init__.py` | Package exports, report registry |
| `positions.py` | Position summary: all open positions with P&L |
| `pnl.py` | P&L decomposition: per-market, total, cash balance |
| `risk.py` | Risk status: limits, exposure, drawdown, daily loss |
| `dashboard.py` | Combined dashboard: positions + P&L + risk in one view |

### 2. CLI Integration

```bash
polymind report positions     # Show position summary
polymind report pnl           # Show P&L breakdown
polymind report risk          # Show risk status
polymind report dashboard     # Show combined dashboard (default)
```

### 3. Data Sources

- **LedgerStore**: positions, P&L, cash balance, fill history
- **RiskManager**: position sizing, drawdown, daily loss
- **LimitsManager**: position limits, order rate, exposure, daily loss

## Interfaces

```python
class PositionReport:
    market_id: str
    outcome: str
    size: float
    avg_entry: float
    unrealized_pnl: float
    realized_pnl: float
    current_price: float | None

class PnlReport:
    market_id: str
    realized_pnl: float
    total_cash: float
    positions_count: int

class RiskReport:
    total_exposure: float
    max_exposure: float
    drawdown_pct: float
    daily_loss: float
    max_daily_loss: float
    is_healthy: bool
```

## Testing

- Unit tests for each report module with mocked stores
- Integration test for CLI commands
- All existing tests must continue to pass
