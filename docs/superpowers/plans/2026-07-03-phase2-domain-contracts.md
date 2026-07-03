# Phase 2 Domain Contracts Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Freeze five missing domain contracts (PortfolioTarget, FillEvent, LedgerEntry, RiskDecision, WorkflowCommand) for Phase 2 of the Polymind architecture roadmap.

**Architecture:** Plain dataclasses in separate modules under `polymind/core/`, following the established patterns in `intents.py`. Each contract is its own file with a clear responsibility. Tests follow TDD with the same pattern as `tests/test_intents.py`.

**Tech Stack:** Python 3.10+, dataclasses, enums, ABCs, pytest-asyncio.

## Global Constraints

- Line length 100 (black/ruff config).
- `from __future__ import annotations` at top of every module.
- Timestamps use `datetime.now(timezone.utc)` via `field(default_factory=...)` in dataclasses.
- No imports from `polymind.core` modules that don't exist yet (all five new modules are independent).
- Existing `OrderSide`, `StrategyIntent` re-used from `polymind.core.intents`.
- Every new module has a corresponding `tests/test_*.py` with complete TDD coverage.
- Commit message prefix: `feat(core): add <module>`.

---
### Task 1: PortfolioTarget — portfolio target contract

**Files:**
- Create: `polymind/core/portfolio.py`
- Create: `tests/test_portfolio.py`
- Modify: `polymind/core/__init__.py` (export new types)

**Interfaces:**
- Consumes: nothing new (standalone types)
- Produces: `PortfolioTarget`, `PositionDirection`

- [ ] **Step 1: Write the failing test**

```python
"""
Tests for PortfolioTarget and PositionDirection.
"""

from __future__ import annotations

from typing import Any, Dict

import pytest

from polymind.core.portfolio import PortfolioTarget, PositionDirection


class TestPositionDirection:
    def test_enum_values_present(self):
        assert PositionDirection.LONG.value == 1
        assert PositionDirection.SHORT.value == 2
        assert PositionDirection.NEUTRAL.value == 3

    def test_enum_inequality(self):
        assert PositionDirection.LONG != PositionDirection.SHORT


class TestPortfolioTarget:
    def test_minimal_construction(self):
        target = PortfolioTarget(
            market_id="0xabc",
            direction=PositionDirection.LONG,
            target_size=100.0,
            confidence=0.75,
            rank=1,
        )
        assert target.market_id == "0xabc"
        assert target.direction == PositionDirection.LONG
        assert target.target_size == 100.0
        assert target.confidence == 0.75
        assert target.rank == 1
        assert target.holding_period_hours is None
        assert target.reason == ""

    def test_full_construction(self):
        target = PortfolioTarget(
            market_id="0xdef",
            direction=PositionDirection.SHORT,
            target_size=50.0,
            confidence=0.3,
            rank=9,
            holding_period_hours=24.0,
            reason="weak momentum signal",
            metadata={"signal_id": "mom_7d"},
        )
        assert target.holding_period_hours == 24.0
        assert target.reason == "weak momentum signal"
        assert target.metadata["signal_id"] == "mom_7d"

    def test_neutral_direction(self):
        target = PortfolioTarget(
            market_id="0xabc",
            direction=PositionDirection.NEUTRAL,
            target_size=0.0,
            confidence=0.5,
            rank=5,
        )
        assert target.direction == PositionDirection.NEUTRAL
        assert target.target_size == 0.0
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /home/debian/pmdata/polymind && python -m pytest tests/test_portfolio.py -v
```
Expected: FAIL — ModuleNotFoundError or ImportError (portfolio.py doesn't exist yet)

- [ ] **Step 3: Write minimal implementation**

Create `polymind/core/portfolio.py`:
```python
"""
Portfolio target contracts (Phase 2).

Factor strategies produce PortfolioTargets as the output of their
portfolio construction step.  An execution bridge converts these into
OrderIntents for the executor.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any, Dict, Optional


class PositionDirection(Enum):
    """Direction of a portfolio position."""

    LONG = auto()
    SHORT = auto()
    NEUTRAL = auto()


@dataclass
class PortfolioTarget:
    """A desired portfolio position produced by a factor or overlay strategy."""

    market_id: str
    direction: PositionDirection
    target_size: float  # in token/shares (not USD)
    confidence: float  # 0.0–1.0, from signal score
    rank: int  # decile / percentile rank among universe
    holding_period_hours: Optional[float] = None
    reason: str = ""
    metadata: Dict[str, Any] = field(default_factory=dict)
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd /home/debian/pmdata/polymind && python -m pytest tests/test_portfolio.py -v
```
Expected: PASS (3 passed)

- [ ] **Step 5: Update `polymind/core/__init__.py`**

Add to imports:
```python
from polymind.core.portfolio import PortfolioTarget, PositionDirection
```

Add to `__all__`:
```python
"PortfolioTarget",
"PositionDirection",
```

- [ ] **Step 6: Commit**

```bash
cd /home/debian/pmdata/polymind && git add polymind/core/portfolio.py tests/test_portfolio.py polymind/core/__init__.py
git commit -m "feat(core): add PortfolioTarget and PositionDirection contracts"
```

---
### Task 2: FillEvent — fill event contract

**Files:**
- Create: `polymind/core/fills.py`
- Create: `tests/test_fills.py`
- Modify: `polymind/core/__init__.py` (export new types)

**Interfaces:**
- Consumes: `OrderSide` from `polymind.core.intents`
- Produces: `FillEvent`, `FillSource`

- [ ] **Step 1: Write the failing test**

```python
"""
Tests for FillEvent and FillSource.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from polymind.core.fills import FillEvent, FillSource
from polymind.core.intents import OrderSide


class TestFillSource:
    def test_enum_values(self):
        assert FillSource.WEBSOCKET != FillSource.CLOB_API
        assert FillSource.ONCHAIN != FillSource.SIMULATED

    def test_all_sources_defined(self):
        expected = {"WEBSOCKET", "CLOB_API", "ONCHAIN", "SIMULATED"}
        assert {e.name for e in FillSource} == expected


class TestFillEvent:
    def test_minimal_construction(self):
        now = datetime.now(timezone.utc)
        event = FillEvent(
            fill_id="fill-001",
            market_id="0xabc",
            outcome="YES",
            side=OrderSide.BUY,
            price=0.85,
            size=10.0,
            fee=0.01,
            timestamp=now,
            source=FillSource.WEBSOCKET,
        )
        assert event.fill_id == "fill-001"
        assert event.market_id == "0xabc"
        assert event.outcome == "YES"
        assert event.side == OrderSide.BUY
        assert event.price == 0.85
        assert event.size == 10.0
        assert event.fee == 0.01
        assert event.timestamp == now
        assert event.source == FillSource.WEBSOCKET
        assert event.order_id is None
        assert event.taker is False

    def test_full_construction(self):
        now = datetime.now(timezone.utc)
        event = FillEvent(
            fill_id="fill-002",
            market_id="0xdef",
            outcome="NO",
            side=OrderSide.SELL,
            price=0.12,
            size=5.0,
            fee=0.005,
            timestamp=now,
            source=FillSource.CLOB_API,
            order_id="ord-456",
            taker=True,
            metadata={"retry_count": 0},
        )
        assert event.order_id == "ord-456"
        assert event.taker is True
        assert event.metadata["retry_count"] == 0

    def test_simulated_source(self):
        now = datetime.now(timezone.utc)
        event = FillEvent(
            fill_id="fill-sim-001",
            market_id="0xabc",
            outcome="YES",
            side=OrderSide.BUY,
            price=0.80,
            size=100.0,
            fee=0.0,
            timestamp=now,
            source=FillSource.SIMULATED,
        )
        assert event.source == FillSource.SIMULATED
        assert event.fee == 0.0
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /home/debian/pmdata/polymind && python -m pytest tests/test_fills.py -v
```
Expected: FAIL — ModuleNotFoundError or ImportError

- [ ] **Step 3: Write minimal implementation**

Create `polymind/core/fills.py`:
```python
"""
Fill event contracts (Phase 2).

A unified representation of a fill or partial fill, regardless of whether
it was detected via WebSocket event, CLOB API poll, or on-chain balance
reconciliation.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Any, Dict, Optional

from polymind.core.intents import OrderSide


class FillSource(Enum):
    """Origin of a fill detection."""

    WEBSOCKET = auto()
    CLOB_API = auto()
    ONCHAIN = auto()
    SIMULATED = auto()


@dataclass
class FillEvent:
    """A fill or partial fill detected by any channel."""

    fill_id: str
    market_id: str
    outcome: str  # "YES" or "NO"
    side: OrderSide
    price: float
    size: float
    fee: float
    timestamp: datetime
    source: FillSource
    order_id: Optional[str] = None
    taker: bool = False
    metadata: Dict[str, Any] = field(default_factory=dict)
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd /home/debian/pmdata/polymind && python -m pytest tests/test_fills.py -v
```
Expected: PASS (3 passed)

- [ ] **Step 5: Update `polymind/core/__init__.py`**

Add to imports:
```python
from polymind.core.fills import FillEvent, FillSource
```

Add to `__all__`:
```python
"FillEvent",
"FillSource",
```

- [ ] **Step 6: Commit**

```bash
cd /home/debian/pmdata/polymind && git add polymind/core/fills.py tests/test_fills.py polymind/core/__init__.py
git commit -m "feat(core): add FillEvent and FillSource contracts"
```

---
### Task 3: LedgerEntry — ledger entry contract

**Files:**
- Create: `polymind/core/ledger.py`
- Create: `tests/test_ledger.py`
- Modify: `polymind/core/__init__.py` (export new types)

**Interfaces:**
- Consumes: nothing new (standalone types)
- Produces: `LedgerEntry`, `EntryType`

- [ ] **Step 1: Write the failing test**

```python
"""
Tests for LedgerEntry and EntryType.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from polymind.core.ledger import EntryType, LedgerEntry


class TestEntryType:
    def test_enum_values(self):
        assert EntryType.FILL != EntryType.FEE
        assert EntryType.MERGE != EntryType.SPLIT

    def test_correction_type_exists(self):
        assert EntryType.CORRECTION in EntryType

    def test_all_types_defined(self):
        expected = {
            "FILL", "FEE", "MERGE", "SPLIT", "REDEEM",
            "CASH_ADJUSTMENT", "CORRECTION",
        }
        assert {e.name for e in EntryType} == expected


class TestLedgerEntry:
    def test_minimal_construction(self):
        now = datetime.now(timezone.utc)
        entry = LedgerEntry(
            entry_id="ledger-001",
            entry_type=EntryType.FILL,
            timestamp=now,
            market_id="0xabc",
            description="Bought 10 YES @ 0.85",
            delta_cash=-8.51,  # -price*size - fee
            delta_position=10.0,
            position_after=10.0,
            cash_after=991.49,
        )
        assert entry.entry_id == "ledger-001"
        assert entry.entry_type == EntryType.FILL
        assert entry.timestamp == now
        assert entry.market_id == "0xabc"
        assert entry.delta_cash == -8.51
        assert entry.delta_position == 10.0
        assert entry.position_after == 10.0
        assert entry.cash_after == 991.49
        assert entry.fill_ref is None
        assert entry.supersedes is None

    def test_fill_reference(self):
        now = datetime.now(timezone.utc)
        entry = LedgerEntry(
            entry_id="ledger-002",
            entry_type=EntryType.FILL,
            timestamp=now,
            market_id="0xabc",
            description="Sold 5 YES @ 0.90",
            delta_cash=4.49,
            delta_position=-5.0,
            position_after=5.0,
            cash_after=995.98,
            fill_ref="fill-001",
        )
        assert entry.fill_ref == "fill-001"

    def test_supersedes_chain(self):
        now = datetime.now(timezone.utc)
        original = LedgerEntry(
            entry_id="ledger-001",
            entry_type=EntryType.FILL,
            timestamp=now,
            market_id="0xabc",
            description="Original entry",
            delta_cash=-8.50,
            delta_position=10.0,
            position_after=10.0,
            cash_after=991.50,
        )
        corrected = LedgerEntry(
            entry_id="ledger-003",
            entry_type=EntryType.CORRECTION,
            timestamp=now,
            market_id="0xabc",
            description="Corrected fee",
            delta_cash=-8.51,
            delta_position=10.0,
            position_after=10.0,
            cash_after=991.49,
            supersedes="ledger-001",
        )
        assert corrected.supersedes == original.entry_id

    def test_cash_adjustment_entry(self):
        now = datetime.now(timezone.utc)
        entry = LedgerEntry(
            entry_id="ledger-004",
            entry_type=EntryType.CASH_ADJUSTMENT,
            timestamp=now,
            market_id="GLOBAL",
            description="Deposit 500 USDC",
            delta_cash=500.0,
            delta_position=0.0,
            position_after=0.0,
            cash_after=1500.0,
        )
        assert entry.entry_type == EntryType.CASH_ADJUSTMENT
        assert entry.delta_position == 0.0
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /home/debian/pmdata/polymind && python -m pytest tests/test_ledger.py -v
```
Expected: FAIL — ModuleNotFoundError

- [ ] **Step 3: Write minimal implementation**

Create `polymind/core/ledger.py`:
```python
"""
Ledger entry contracts (Phase 2).

Append-only entries in the paper or live P&L ledger, recording fills,
fees, merges, splits, redemptions, and cash adjustments.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto
from typing import Any, Dict, Optional


class EntryType(Enum):
    """Category of a ledger entry."""

    FILL = auto()
    FEE = auto()
    MERGE = auto()
    SPLIT = auto()
    REDEEM = auto()
    CASH_ADJUSTMENT = auto()
    CORRECTION = auto()


@dataclass
class LedgerEntry:
    """Immutable record of a value-changing event.

    The ledger is append-only. Once written, an entry is never mutated;
    corrections produce new entries with a reference to the superseded one.
    """

    entry_id: str
    entry_type: EntryType
    timestamp: datetime
    market_id: str
    description: str
    delta_cash: float
    delta_position: float
    position_after: float
    cash_after: float
    fill_ref: Optional[str] = None
    supersedes: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd /home/debian/pmdata/polymind && python -m pytest tests/test_ledger.py -v
```
Expected: PASS (4 passed)

- [ ] **Step 5: Update `polymind/core/__init__.py`**

Add to imports:
```python
from polymind.core.ledger import EntryType, LedgerEntry
```

Add to `__all__`:
```python
"EntryType",
"LedgerEntry",
```

- [ ] **Step 6: Commit**

```bash
cd /home/debian/pmdata/polymind && git add polymind/core/ledger.py tests/test_ledger.py polymind/core/__init__.py
git commit -m "feat(core): add LedgerEntry and EntryType contracts"
```

---
### Task 4: RiskDecision — risk contracts

**Files:**
- Create: `polymind/core/risk.py`
- Create: `tests/test_risk.py`
- Modify: `polymind/core/__init__.py` (export new types)

**Interfaces:**
- Consumes: `StrategyIntent` from `polymind.core.intents`
- Produces: `RiskDecision`, `RiskGate`, `RiskContext`

- [ ] **Step 1: Write the failing test**

```python
"""
Tests for RiskDecision, RiskGate, and RiskContext.
"""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict

import pytest

from polymind.core.intents import OrderIntent, OrderSide, StrategyIntent
from polymind.core.risk import RiskContext, RiskDecision, RiskGate


class TestRiskDecision:
    def test_approved_decision(self):
        decision = RiskDecision(
            gate_name="exposure_limit",
            approved=True,
            reason="Within limits",
        )
        assert decision.gate_name == "exposure_limit"
        assert decision.approved is True
        assert decision.reason == "Within limits"
        assert decision.timestamp is not None

    def test_rejected_decision(self):
        decision = RiskDecision(
            gate_name="drawdown_guard",
            approved=False,
            reason="Daily loss limit exceeded",
            overrides={"reduce_size_pct": 50.0},
        )
        assert decision.approved is False
        assert decision.overrides == {"reduce_size_pct": 50.0}

    def test_timestamp_auto_set(self):
        before = datetime.now(timezone.utc)
        decision = RiskDecision(gate_name="kill_switch", approved=True, reason="All clear")
        after = datetime.now(timezone.utc)
        assert before <= decision.timestamp <= after


class TestRiskContext:
    def test_full_construction(self):
        ctx = RiskContext(
            current_positions={"0xabc": 10.0},
            current_exposure=500.0,
            daily_pnl=-25.0,
            is_kill_switch_active=False,
            portfolio_value=1000.0,
        )
        assert ctx.current_positions["0xabc"] == 10.0
        assert ctx.current_exposure == 500.0
        assert ctx.daily_pnl == -25.0
        assert ctx.is_kill_switch_active is False
        assert ctx.portfolio_value == 1000.0

    def test_kill_switch_active(self):
        ctx = RiskContext(
            current_positions={},
            current_exposure=0.0,
            daily_pnl=0.0,
            is_kill_switch_active=True,
            portfolio_value=1000.0,
        )
        assert ctx.is_kill_switch_active is True


class TestRiskGate:
    @pytest.mark.asyncio
    async def test_gate_can_approve(self):
        gate = AllowAllGate()
        now = datetime.now(timezone.utc)
        intent = StrategyIntent(timestamp=now, strategy_name="test")
        ctx = RiskContext(
            current_positions={},
            current_exposure=0.0,
            daily_pnl=0.0,
            is_kill_switch_active=False,
            portfolio_value=1000.0,
        )
        decision = await gate.evaluate(intent, ctx)
        assert decision.approved is True

    @pytest.mark.asyncio
    async def test_gate_can_reject(self):
        gate = RejectAllGate()
        now = datetime.now(timezone.utc)
        intent = StrategyIntent(timestamp=now, strategy_name="test")
        ctx = RiskContext(
            current_positions={},
            current_exposure=0.0,
            daily_pnl=0.0,
            is_kill_switch_active=True,
            portfolio_value=1000.0,
        )
        decision = await gate.evaluate(intent, ctx)
        assert decision.approved is False

    @pytest.mark.asyncio
    async def test_gate_name_preserved(self):
        gate = AllowAllGate()
        now = datetime.now(timezone.utc)
        intent = StrategyIntent(timestamp=now, strategy_name="test")
        ctx = RiskContext(
            current_positions={},
            current_exposure=0.0,
            daily_pnl=0.0,
            is_kill_switch_active=False,
            portfolio_value=1000.0,
        )
        decision = await gate.evaluate(intent, ctx)
        assert decision.gate_name == "AllowAllGate"


class AllowAllGate(RiskGate):
    """Test gate that always approves."""
    name = "AllowAllGate"

    async def evaluate(self, intent: StrategyIntent, context: RiskContext) -> RiskDecision:
        return RiskDecision(
            gate_name=self.name,
            approved=True,
            reason="Always allow (test)",
        )


class RejectAllGate(RiskGate):
    """Test gate that always rejects."""
    name = "RejectAllGate"

    async def evaluate(self, intent: StrategyIntent, context: RiskContext) -> RiskDecision:
        return RiskDecision(
            gate_name=self.name,
            approved=False,
            reason="Always reject (test)",
        )
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /home/debian/pmdata/polymind && python -m pytest tests/test_risk.py -v
```
Expected: FAIL — ModuleNotFoundError

- [ ] **Step 3: Write minimal implementation**

Create `polymind/core/risk.py`:
```python
"""
Risk decision contracts (Phase 2).

Risk gates sit between strategy decisions and execution. Each gate inspects
a StrategyIntent and returns a RiskDecision.  Gates are composable and
independent.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from polymind.core.intents import StrategyIntent


@dataclass
class RiskDecision:
    """Decision from a single risk gate."""

    gate_name: str
    approved: bool
    reason: str
    overrides: Optional[Dict[str, float]] = None
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))


@dataclass
class RiskContext:
    """Context provided to every risk gate."""

    current_positions: Dict[str, float]
    current_exposure: float
    daily_pnl: float
    is_kill_switch_active: bool
    portfolio_value: float


class RiskGate(ABC):
    """A single composable risk check."""

    name: str

    @abstractmethod
    async def evaluate(
        self,
        intent: StrategyIntent,
        context: RiskContext,
    ) -> RiskDecision:
        ...
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd /home/debian/pmdata/polymind && python -m pytest tests/test_risk.py -v
```
Expected: PASS (6 passed)

- [ ] **Step 5: Update `polymind/core/__init__.py`**

Add to imports:
```python
from polymind.core.risk import RiskContext, RiskDecision, RiskGate
```

Add to `__all__`:
```python
"RiskContext",
"RiskDecision",
"RiskGate",
```

- [ ] **Step 6: Commit**

```bash
cd /home/debian/pmdata/polymind && git add polymind/core/risk.py tests/test_risk.py polymind/core/__init__.py
git commit -m "feat(core): add RiskDecision, RiskGate, and RiskContext contracts"
```

---
### Task 5: WorkflowCommand — workflow command contract

**Files:**
- Create: `polymind/core/workflows.py`
- Create: `tests/test_workflows.py`
- Modify: `polymind/core/__init__.py` (export new types)

**Interfaces:**
- Consumes: nothing new (standalone types)
- Produces: `WorkflowCommand`, `CommandType`

- [ ] **Step 1: Write the failing test**

```python
"""
Tests for WorkflowCommand and CommandType.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from polymind.core.workflows import CommandType, WorkflowCommand


class TestCommandType:
    def test_lifecycle_commands(self):
        assert CommandType.START != CommandType.STOP
        assert CommandType.PAUSE != CommandType.RESUME

    def test_pair_lifecycle_commands(self):
        assert CommandType.SPLIT in CommandType
        assert CommandType.MERGE in CommandType
        assert CommandType.REDEEM in CommandType
        assert CommandType.SELL_REMAINDER in CommandType
        assert CommandType.ONE_SIDED_HALT in CommandType

    def test_all_commands_defined(self):
        expected = {
            "START", "STOP", "PAUSE", "RESUME", "RESTART",
            "SPLIT", "MERGE", "REDEEM", "SELL_REMAINDER",
            "ONE_SIDED_HALT",
        }
        assert {e.name for e in CommandType} == expected


class TestWorkflowCommand:
    def test_minimal_construction(self):
        cmd = WorkflowCommand(
            workflow_id="wf-amm-001",
            command=CommandType.START,
            reason="Starting AMM strategy",
        )
        assert cmd.workflow_id == "wf-amm-001"
        assert cmd.command == CommandType.START
        assert cmd.reason == "Starting AMM strategy"
        assert cmd.timestamp is not None
        assert cmd.params == {}

    def test_stop_command(self):
        cmd = WorkflowCommand(
            workflow_id="wf-event-002",
            command=CommandType.STOP,
            reason="Max drawdown reached",
        )
        assert cmd.reason == "Max drawdown reached"
        assert cmd.params == {}

    def test_with_params(self):
        cmd = WorkflowCommand(
            workflow_id="wf-maker-rebate-003",
            command=CommandType.MERGE,
            reason="Scheduled merge",
            params={"outcome": "YES", "token_ids": ["123", "456"]},
        )
        assert cmd.params["outcome"] == "YES"
        assert cmd.params["token_ids"] == ["123", "456"]

    def test_timestamp_auto_set(self):
        before = datetime.now(timezone.utc)
        cmd = WorkflowCommand(
            workflow_id="wf-test",
            command=CommandType.START,
            reason="test",
        )
        after = datetime.now(timezone.utc)
        assert before <= cmd.timestamp <= after

    def test_restart_command(self):
        cmd = WorkflowCommand(
            workflow_id="wf-bands-004",
            command=CommandType.RESTART,
            reason="Reconnecting after disconnect",
        )
        assert cmd.command == CommandType.RESTART
```

- [ ] **Step 2: Run test to verify it fails**

```bash
cd /home/debian/pmdata/polymind && python -m pytest tests/test_workflows.py -v
```
Expected: FAIL — ModuleNotFoundError

- [ ] **Step 3: Write minimal implementation**

Create `polymind/core/workflows.py`:
```python
"""
Workflow command contracts (Phase 2).

WorkflowCommand represents a lifecycle or pair-management command for a
workflow instance.  The workflow runtime interprets the command and
translates it into lower-level intents.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum, auto
from typing import Any, Dict


class CommandType(Enum):
    """Category of a workflow command."""

    # Lifecycle
    START = auto()
    STOP = auto()
    PAUSE = auto()
    RESUME = auto()
    RESTART = auto()

    # Pair lifecycle (for Maker Rebate, Event MM etc.)
    SPLIT = auto()
    MERGE = auto()
    REDEEM = auto()
    SELL_REMAINDER = auto()
    ONE_SIDED_HALT = auto()


@dataclass
class WorkflowCommand:
    """A workflow lifecycle or pair-management command."""

    workflow_id: str
    command: CommandType
    reason: str = ""
    params: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
```

- [ ] **Step 4: Run test to verify it passes**

```bash
cd /home/debian/pmdata/polymind && python -m pytest tests/test_workflows.py -v
```
Expected: PASS (5 passed)

- [ ] **Step 5: Update `polymind/core/__init__.py`**

Add to imports:
```python
from polymind.core.workflows import CommandType, WorkflowCommand
```

Add to `__all__`:
```python
"CommandType",
"WorkflowCommand",
```

- [ ] **Step 6: Commit**

```bash
cd /home/debian/pmdata/polymind && git add polymind/core/workflows.py tests/test_workflows.py polymind/core/__init__.py
git commit -m "feat(core): add WorkflowCommand and CommandType contracts"
```

---
### Task 6: Final verification and export cleanup

**Files:**
- Modify: `polymind/core/__init__.py` (final `__all__` audit)

- [ ] **Step 1: Verify all imports work**

```bash
cd /home/debian/pmdata/polymind && python -c "
from polymind.core.portfolio import PortfolioTarget, PositionDirection
from polymind.core.fills import FillEvent, FillSource
from polymind.core.ledger import EntryType, LedgerEntry
from polymind.core.risk import RiskContext, RiskDecision, RiskGate
from polymind.core.workflows import CommandType, WorkflowCommand
from polymind.core.intents import OrderIntent, CancelIntent, StrategyIntent
print('All Phase 2 contracts import successfully')
"
```
Expected: `All Phase 2 contracts import successfully`

- [ ] **Step 2: Run full test suite**

```bash
cd /home/debian/pmdata/polymind && python -m pytest tests/ -v --tb=short
```
Expected: All tests pass

- [ ] **Step 3: Read final `polymind/core/__init__.py` and verify `__all__` is complete**

Check that `__all__` exports all new types alongside the existing ones.

- [ ] **Step 4: Commit any final touch-ups**

```bash
cd /home/debian/pmdata/polymind && git add -A && git commit -m "chore: finalize Phase 2 domain contracts export audit" || echo "nothing to commit"
```
