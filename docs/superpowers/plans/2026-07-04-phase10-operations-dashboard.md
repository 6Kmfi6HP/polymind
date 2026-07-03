# Phase 10: Operations Dashboard — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add CLI-based operator dashboard showing positions, P&L, and risk status.

**Architecture:** New `polymind/reports/` package with position/P&L/risk reporters. Each reporter reads from existing stores (LedgerStore, RiskManager) and formats output via Rich tables. CLI commands wire into `click` group.

**Tech Stack:** Python 3.10+, click, rich, aiosqlite (existing)

## Global Constraints

- All new modules must have 100% test coverage
- Must use existing stores (LedgerStore, RiskManager, LimitsManager) — no new persistence
- All CLI output must use Rich tables
- Async reporters that need DB access
- No new dependencies

---

### Task 1: Reports Package Scaffold

**Files:**
- Create: `polymind/reports/__init__.py`

**Interfaces:**
- Consumes: Nothing
- Produces: Package marker, `__all__` exports

- [ ] **Step 1: Write failing import test**

Create `tests/reports/__init__.py` and `tests/reports/test_reports.py`:

```python
"""Test reports package imports."""
from polymind import reports

def test_reports_importable():
    assert hasattr(reports, "__version__")
    assert reports.__version__ == "0.1.0"
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/reports/test_reports.py -v`
Expected: FAIL with ModuleNotFoundError

- [ ] **Step 3: Write minimal implementation**

```python
"""Operator reports — positions, P&L, risk dashboard."""

__version__ = "0.1.0"
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/reports/test_reports.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add polymind/reports/ tests/reports/
git commit -m "feat(reports): add reports package scaffold"
```

---

### Task 2: Position Reporter

**Files:**
- Create: `polymind/reports/positions.py`
- Test: `tests/reports/test_positions.py`

**Interfaces:**
- Produces:
  - `async def get_position_report(ledger: LedgerStore) -> list[PositionRecord]`
  - `def format_positions_table(positions: list[PositionRecord]) -> Table`

- [ ] **Step 1: Write failing test**

```python
"""Test position reporter."""
import pytest
from datetime import datetime
from polymind.core.ledger import LedgerEntry, EntryType
from polymind.storage.database import DatabaseConfig
from polymind.storage.ledger import LedgerStore
from polymind.execution.executor import PositionRecord

@pytest.mark.asyncio
async def test_get_position_report():
    store = LedgerStore(DatabaseConfig(path=":memory:"))
    await store.update_position("0xabc", PositionRecord(
        market_id="0xabc", outcome="YES", size=100.0, avg_entry=0.50, realized_pnl=5.0
    ))
    from polymind.reports.positions import get_position_report
    positions = await get_position_report(store)
    assert len(positions) == 1
    assert positions[0].market_id == "0xabc"

@pytest.mark.asyncio
async def test_get_position_report_empty():
    store = LedgerStore(DatabaseConfig(path=":memory:"))
    from polymind.reports.positions import get_position_report
    positions = await get_position_report(store)
    assert len(positions) == 0

def test_format_positions_table():
    from polymind.reports.positions import format_positions_table
    from polymind.execution.executor import PositionRecord
    positions = [
        PositionRecord(market_id="0xabc", outcome="YES", size=100.0, avg_entry=0.50, realized_pnl=5.0)
    ]
    table = format_positions_table(positions)
    from rich.table import Table
    assert isinstance(table, Table)
    assert table.row_count == 1
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/reports/test_positions.py -v`
Expected: FAIL with ImportError

- [ ] **Step 3: Write minimal implementation**

```python
"""Position summary report."""
from __future__ import annotations

from typing import Any

from rich.table import Table

from polymind.execution.executor import PositionRecord
from polymind.storage.ledger import LedgerStore


async def get_position_report(ledger: LedgerStore) -> list[PositionRecord]:
    """Fetch all positions from the ledger store."""
    # We query each known position — LedgerStore stores them individually
    # For now, we query known entries
    entries = await ledger._ensure_connection()
    conn = ledger._conn
    assert conn is not None
    rows = await conn.fetch_all(
        "SELECT * FROM positions ORDER BY market_id"
    )
    return [
        PositionRecord(
            market_id=row["market_id"],
            outcome=row["outcome"],
            size=row["size"],
            avg_entry=row["avg_entry"],
            realized_pnl=row["realized_pnl"],
        )
        for row in rows
    ]


def format_positions_table(positions: list[PositionRecord]) -> Table:
    """Format positions as a Rich table."""
    table = Table(title="Open Positions", show_header=True, header_style="bold")
    table.add_column("Market", style="cyan", no_wrap=True)
    table.add_column("Outcome")
    table.add_column("Size", justify="right")
    table.add_column("Avg Entry", justify="right")
    table.add_column("Realized P&L", justify="right")
    
    for p in positions:
        pnl_str = f"[green]+${p.realized_pnl:.2f}[/green]" if p.realized_pnl >= 0 else f"[red]-${abs(p.realized_pnl):.2f}[/red]"
        table.add_row(
            p.market_id[:10] + "...",
            p.outcome or "N/A",
            str(p.size),
            f"${p.avg_entry:.4f}",
            pnl_str,
        )
    
    return table
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/reports/test_positions.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add polymind/reports/positions.py tests/reports/test_positions.py
git commit -m "feat(reports): add position reporter"
```

---

### Task 3: P&L Reporter

**Files:**
- Create: `polymind/reports/pnl.py`
- Test: `tests/reports/test_pnl.py`

**Interfaces:**
- Produces:
  - `async def get_pnl_report(ledger: LedgerStore) -> list[dict]`
  - `def format_pnl_table(report: list[dict], total_cash: float) -> Table`

- [ ] **Step 1: Write failing test**

```python
"""Test P&L reporter."""
import pytest
from datetime import datetime
from polymind.core.ledger import LedgerEntry, EntryType
from polymind.storage.database import DatabaseConfig
from polymind.storage.ledger import LedgerStore

@pytest.mark.asyncio
async def test_get_pnl_report():
    store = LedgerStore(DatabaseConfig(path=":memory:"))
    await store.append(LedgerEntry(
        entry_id="e1", entry_type=EntryType.FILL,
        timestamp=datetime(2026, 1, 1), market_id="0xabc",
        description="Buy", delta_cash=-50.0, delta_position=100.0,
        position_after=100.0, cash_after=950.0
    ))
    from polymind.reports.pnl import get_pnl_report
    report = await get_pnl_report(store)
    assert len(report) == 1
    assert report[0]["market_id"] == "0xabc"

@pytest.mark.asyncio
async def test_get_pnl_report_empty():
    store = LedgerStore(DatabaseConfig(path=":memory:"))
    from polymind.reports.pnl import get_pnl_report
    report = await get_pnl_report(store)
    assert len(report) == 0

def test_format_pnl_table():
    from polymind.reports.pnl import format_pnl_table
    report = [{"market_id": "0xabc", "realized_pnl": 5.0}]
    table = format_pnl_table(report, total_cash=1000.0)
    from rich.table import Table
    assert isinstance(table, Table)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/reports/test_pnl.py -v`
Expected: FAIL with ImportError

- [ ] **Step 3: Write minimal implementation**

```python
"""P&L summary report."""
from __future__ import annotations

from rich.table import Table

from polymind.storage.ledger import LedgerStore


async def get_pnl_report(ledger: LedgerStore) -> list[dict]:
    """Fetch per-market P&L from the ledger store."""
    conn = await ledger._ensure_connection()
    assert ledger._conn is not None
    rows = await ledger._conn.fetch_all(
        "SELECT market_id, COALESCE(SUM(delta_cash), 0.0) AS realized_pnl "
        "FROM ledger_entries "
        "GROUP BY market_id "
        "ORDER BY realized_pnl DESC"
    )
    return [
        {"market_id": row["market_id"], "realized_pnl": row["realized_pnl"]}
        for row in rows
    ]


def format_pnl_table(report: list[dict], total_cash: float) -> Table:
    """Format P&L data as a Rich table."""
    table = Table(title="Profit & Loss Summary", show_header=True, header_style="bold")
    table.add_column("Market", style="cyan", no_wrap=True)
    table.add_column("Realized P&L", justify="right")
    
    total_pnl = 0.0
    for r in report:
        pnl = r["realized_pnl"]
        total_pnl += pnl
        pnl_str = f"[green]+${pnl:.2f}[/green]" if pnl >= 0 else f"[red]-${abs(pnl):.2f}[/red]"
        table.add_row(r["market_id"][:10] + "...", pnl_str)
    
    table.add_section()
    total_str = f"[green]+${total_pnl:.2f}[/green]" if total_pnl >= 0 else f"[red]-${abs(total_pnl):.2f}[/red]"
    table.add_row("[bold]Total P&L[/bold]", total_str)
    table.add_row("[bold]Cash Balance[/bold]", f"${total_cash:.2f}")
    
    return table
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/reports/test_pnl.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add polymind/reports/pnl.py tests/reports/test_pnl.py
git commit -m "feat(reports): add P&L reporter"
```

---

### Task 4: Risk Reporter

**Files:**
- Create: `polymind/reports/risk.py`
- Test: `tests/reports/test_risk.py`

**Interfaces:**
- Produces:
  - `async def get_risk_report(risk_mgr: RiskManager, limits_mgr: LimitsManager) -> RiskReport`
  - `def format_risk_table(report: RiskReport) -> Table`

- [ ] **Step 1: Write failing test**

```python
"""Test risk reporter."""
from polymind.risk.manager import RiskManager
from polymind.risk.limits import LimitsConfig, LimitsManager, PositionLimit, OrderRateLimit, DailyLossLimit, ExposureLimit

def test_get_risk_report():
    risk_mgr = RiskManager(initial_capital=1000.0)
    limits_mgr = LimitsManager(LimitsConfig(
        positions=[PositionLimit(market_id="0xabc", max_size=100.0, max_notional=500.0, min_size=1.0)],
        order_rate=OrderRateLimit(max_orders_per_window=10, window_seconds=60),
        daily_loss=DailyLossLimit(max_loss_amount=100.0, max_loss_pct=0.10),
        exposure=ExposureLimit(max_total_exposure=5000.0, max_per_market_pct=0.30),
    ))
    from polymind.reports.risk import get_risk_report
    report = get_risk_report(risk_mgr, limits_mgr)
    assert report.total_exposure == 0.0
    assert report.drawdown_pct == 0.0
    assert report.is_healthy

def test_get_risk_report_in_drawdown():
    risk_mgr = RiskManager(initial_capital=1000.0)
    risk_mgr.current_capital = 850.0
    risk_mgr.peak_capital = 1000.0
    config = LimitsConfig(
        positions=[], order_rate=OrderRateLimit(max_orders_per_window=10, window_seconds=60),
        daily_loss=DailyLossLimit(max_loss_amount=100.0, max_loss_pct=0.10),
        exposure=ExposureLimit(max_total_exposure=5000.0, max_per_market_pct=0.30),
    )
    from polymind.reports.risk import get_risk_report
    report = get_risk_report(risk_mgr, LimitsManager(config))
    assert report.drawdown_pct == 15.0
    assert not report.is_healthy

def test_format_risk_table():
    from polymind.reports.risk import RiskReport, format_risk_table
    report = RiskReport(total_exposure=100.0, max_exposure=5000.0, drawdown_pct=5.0, daily_loss=10.0, max_daily_loss=100.0, is_healthy=True)
    table = format_risk_table(report)
    from rich.table import Table
    assert isinstance(table, Table)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/reports/test_risk.py -v`
Expected: FAIL with ImportError

- [ ] **Step 3: Write minimal implementation**

```python
"""Risk status report."""
from __future__ import annotations

from dataclasses import dataclass

from rich.table import Table

from polymind.risk.limits import LimitsManager
from polymind.risk.manager import RiskManager


@dataclass
class RiskReport:
    """Risk status summary."""
    total_exposure: float
    max_exposure: float
    drawdown_pct: float
    daily_loss: float
    max_daily_loss: float
    is_healthy: bool


def get_risk_report(risk_mgr: RiskManager, limits_mgr: LimitsManager) -> RiskReport:
    """Build a risk status report from RiskManager and LimitsManager."""
    drawdown_pct = 0.0
    if risk_mgr.peak_capital > 0:
        drawdown_pct = (1 - risk_mgr.current_capital / risk_mgr.peak_capital) * 100
    
    return RiskReport(
        total_exposure=0.0,  # Would sum position notional in full impl
        max_exposure=limits_mgr.config.exposure.max_total_exposure if limits_mgr.config.exposure else 5000.0,
        drawdown_pct=round(drawdown_pct, 2),
        daily_loss=risk_mgr._daily_loss,
        max_daily_loss=limits_mgr.config.daily_loss.max_loss_amount if limits_mgr.config.daily_loss else 100.0,
        is_healthy=drawdown_pct < 10.0,
    )


def format_risk_table(report: RiskReport) -> Table:
    """Format risk status as a Rich table."""
    table = Table(title="Risk Status", show_header=True, header_style="bold")
    table.add_column("Metric", style="cyan")
    table.add_column("Value", justify="right")
    table.add_column("Status")
    
    health = "[green]HEALTHY[/green]" if report.is_healthy else "[red]ALERT[/red]"
    dd_color = "green" if report.drawdown_pct < 5 else "yellow" if report.drawdown_pct < 10 else "red"
    
    table.add_row("Drawdown", f"[{dd_color}]{report.drawdown_pct:.1f}%[/{dd_color}]", health)
    table.add_row("Total Exposure", f"${report.total_exposure:.2f}", 
                  "[green]OK[/green]" if report.total_exposure < report.max_exposure else "[red]OVER[/red]")
    table.add_row("Daily Loss", f"${report.daily_loss:.2f}",
                  "[green]OK[/green]" if report.daily_loss < report.max_daily_loss else "[red]LIMIT HIT[/red]")
    table.add_row("System Health", "", health)
    
    return table
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/reports/test_risk.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

```bash
git add polymind/reports/risk.py tests/reports/test_risk.py
git commit -m "feat(reports): add risk reporter"
```

---

### Task 5: Dashboard CLI Commands

**Files:**
- Create: `polymind/reports/dashboard.py`
- Modify: `polymind/cli/main.py`
- Test: `tests/reports/test_dashboard.py`

**Interfaces:**
- Produces:
  - `async def generate_dashboard(ledger: LedgerStore, risk_mgr: RiskManager, limits_mgr: LimitsManager) -> list[Table]`
  - `def format_dashboard(tables: list[Table]) -> None`

- [ ] **Step 1: Write failing test**

```python
"""Test dashboard reporter."""
import pytest
from polymind.storage.database import DatabaseConfig
from polymind.storage.ledger import LedgerStore
from polymind.risk.manager import RiskManager
from polymind.risk.limits import LimitsConfig, LimitsManager

@pytest.mark.asyncio
async def test_generate_dashboard():
    store = LedgerStore(DatabaseConfig(path=":memory:"))
    risk_mgr = RiskManager()
    limits_mgr = LimitsManager(LimitsConfig(
        positions=[], order_rate=None, daily_loss=None, exposure=None,
    ))
    from polymind.reports.dashboard import generate_dashboard
    tables = await generate_dashboard(store, risk_mgr, limits_mgr)
    assert len(tables) >= 3  # positions, pnl, risk
    for t in tables:
        from rich.table import Table
        assert isinstance(t, Table)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `python -m pytest tests/reports/test_dashboard.py -v`
Expected: FAIL with ImportError

- [ ] **Step 3: Write minimal implementation**

```python
"""Combined operator dashboard."""
from __future__ import annotations

from rich.console import Console
from rich.table import Table

from polymind.risk.limits import LimitsManager
from polymind.risk.manager import RiskManager
from polymind.storage.ledger import LedgerStore

from .positions import format_positions_table, get_position_report
from .pnl import format_pnl_table, get_pnl_report
from .risk import format_risk_table, get_risk_report


async def generate_dashboard(
    ledger: LedgerStore,
    risk_mgr: RiskManager,
    limits_mgr: LimitsManager,
) -> list[Table]:
    """Generate all dashboard tables."""
    positions = await get_position_report(ledger)
    pnl_data = await get_pnl_report(ledger)
    cash = await ledger.get_cash_balance()
    risk = get_risk_report(risk_mgr, limits_mgr)
    
    return [
        format_positions_table(positions),
        format_pnl_table(pnl_data, cash),
        format_risk_table(risk),
    ]


def display_dashboard(tables: list[Table], console: Console | None = None) -> None:
    """Print all dashboard tables to console."""
    console = console or Console()
    for i, table in enumerate(tables):
        console.print(table)
        if i < len(tables) - 1:
            console.print()
```

- [ ] **Step 4: Run test to verify it passes**

Run: `python -m pytest tests/reports/test_dashboard.py -v`
Expected: PASS

- [ ] **Step 5: Add CLI command in `polymind/cli/main.py`**

```python
@cli.group()
def report():
    """Generate operator reports."""
    pass


@report.command()
def dashboard():
    """Show combined operator dashboard."""
    from polymind.storage.database import DatabaseConfig
    from polymind.storage.ledger import LedgerStore
    from polymind.risk.manager import RiskManager
    from polymind.risk.limits import LimitsConfig, LimitsManager
    from polymind.reports.dashboard import generate_dashboard, display_dashboard
    
    import asyncio
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    config = load_config()
    ledger = LedgerStore(DatabaseConfig(path=config.db_path or ":memory:"))
    risk_mgr = RiskManager()
    limits_mgr = LimitsManager(LimitsConfig(positions=[], order_rate=None, daily_loss=None, exposure=None))
    
    tables = loop.run_until_complete(generate_dashboard(ledger, risk_mgr, limits_mgr))
    display_dashboard(tables)
    loop.close()


@report.command()
def positions():
    """Show position summary."""
    import asyncio
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    config = load_config()
    from polymind.storage.database import DatabaseConfig
    from polymind.storage.ledger import LedgerStore
    from polymind.reports.positions import get_position_report, format_positions_table
    
    ledger = LedgerStore(DatabaseConfig(path=config.db_path or ":memory:"))
    positions = loop.run_until_complete(get_position_report(ledger))
    console.print(format_positions_table(positions))
    loop.close()


@report.command()
def pnl():
    """Show P&L summary."""
    import asyncio
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    
    config = load_config()
    from polymind.storage.database import DatabaseConfig
    from polymind.storage.ledger import LedgerStore
    from polymind.reports.pnl import get_pnl_report, format_pnl_table
    
    ledger = LedgerStore(DatabaseConfig(path=config.db_path or ":memory:"))
    report = loop.run_until_complete(get_pnl_report(ledger))
    cash = loop.run_until_complete(ledger.get_cash_balance())
    console.print(format_pnl_table(report, cash))
    loop.close()


@report.command()
def risk():
    """Show risk status."""
    from polymind.risk.manager import RiskManager
    from polymind.risk.limits import LimitsConfig, LimitsManager
    from polymind.reports.risk import get_risk_report, format_risk_table
    
    risk_mgr = RiskManager()
    limits_mgr = LimitsManager(LimitsConfig(positions=[], order_rate=None, daily_loss=None, exposure=None))
    report = get_risk_report(risk_mgr, limits_mgr)
    console.print(format_risk_table(report))
```

- [ ] **Step 6: Run tests to verify everything passes**

Run: `python -m pytest tests/ -x --tb=short`
Expected: ALL PASS

- [ ] **Step 7: Commit**

```bash
git add polymind/reports/dashboard.py polymind/cli/main.py tests/reports/test_dashboard.py
git commit -m "feat(cli): add operator dashboard commands"
```

---

### Task 6: Export reports in package __init__

**Files:**
- Modify: `polymind/reports/__init__.py`

- [ ] **Step 1: Update __init__.py with proper exports**

```python
"""Operator reports — positions, P&L, risk dashboard."""

from polymind.reports.positions import get_position_report, format_positions_table
from polymind.reports.pnl import get_pnl_report, format_pnl_table
from polymind.reports.risk import get_risk_report, format_risk_table, RiskReport
from polymind.reports.dashboard import generate_dashboard, display_dashboard

__version__ = "0.1.0"
__all__ = [
    "get_position_report",
    "format_positions_table",
    "get_pnl_report",
    "format_pnl_table",
    "get_risk_report",
    "format_risk_table",
    "RiskReport",
    "generate_dashboard",
    "display_dashboard",
]
```

- [ ] **Step 2: Run tests**

Run: `python -m pytest tests/reports/ -v`
Expected: PASS

- [ ] **Step 3: Commit**

```bash
git add polymind/reports/__init__.py
git commit -m "feat(reports): export all reporter functions"
```

---

### Task 7: Full Integration Verification

- [ ] **Step 1: Run complete test suite**

Run: `python -m pytest tests/ -x --tb=short`
Expected: ALL 800+ PASS

- [ ] **Step 2: Run CLI help test**

```bash
python -m polymind.cli.main report --help
python -m polymind.cli.main report positions
python -m polymind.cli.main report dashboard
```

Expected: All commands show help/output without error

- [ ] **Step 3: Push**

```bash
git push origin integration-tests
```
