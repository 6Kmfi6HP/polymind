# Phase 22: PairLifecycleManager — Implementation Plan

**Date:** 2026-07-04

---

### Task 1: Create PairLifecycleManager class

**File:** `polymind/polymarket/pair_lifecycle.py`

New module implementing `PairLifecycleManager` with the following components and
behaviour.  All domain types from the design spec are included at the top of the
file so that importers of `polymind.polymarket.pair_lifecycle` get everything
they need from one module.

**1a. Domain types (dataclasses)**

```
PairPosition
    condition_id: str
    yes_token_id: str
    no_token_id: str
    yes_balance: float
    no_balance: float
    yes_avg_entry: float
    no_avg_entry: float
    yes_cost_basis: float
    no_cost_basis: float
    is_resolved: bool = False
    resolved_outcome: str | None = None

SplitOperation
    condition_id: str
    usdc_amount: float
    yes_amount: float
    no_amount: float
    tx_hash: str
    updated_position: PairPosition

MergeOperation
    condition_id: str
    outcome_token_amount: float
    proceeds_usdc: float
    tx_hash: str
    updated_position: PairPosition

RedeemOperation
    condition_id: str
    outcome: str
    amount_redeemed: float
    proceeds_usdc: float
    tx_hash: str
    updated_position: PairPosition

SellRemainderOperation
    market_id: str
    outcome: str
    amount_sold: float
    proceeds_usdc: float
    orders_placed: int

OneSidedHaltResult
    market_id: str
    outcome: str
    orders_cancelled: int
```

**1b. `PairLifecycleError` exception (in `polymind/polymarket/errors.py`)**

Add to `errors.py`:

```python
class InsufficientBalanceError(PolymarketError):
    """Insufficient token or USDC balance for the requested operation."""
    ...

class PairLifecycleError(PolymarketError):
    """Invalid pair-lifecycle operation (e.g., redeem on unresolved market)."""
    ...
```

Then import these into `pair_lifecycle.py`.

**1c. `PairLifecycleManager` class**

Constructor:

```python
class PairLifecycleManager:
    def __init__(
        self,
        gateway: ContractsGateway,
        executor: IntentExecutor | None = None,
    ) -> None:
        self._gateway = gateway
        self._executor = executor
        self._positions: dict[str, PairPosition] = {}      # condition_id -> position
        self._token_id_to_condition: dict[str, str] = {}   # token_id -> condition_id
        self._market_to_condition: dict[str, str] = {}     # market_id -> condition_id
        self._condition_to_market: dict[str, str] = {}     # condition_id -> market_id
```

Inventory methods:

| Method | Signature | Implementation |
|---|---|---|
| `register_market` | `(condition_id, yes_token_id, no_token_id, market_id=None, initial_yes=0, initial_no=0) -> PairPosition` | Create `PairPosition`, insert into `_positions`, update `_token_id_to_condition` for both token IDs. If `market_id` provided, populate `_market_to_condition` and `_condition_to_market`. Raise `PairLifecycleError` if condition_id already registered. |
| `get_position` | `(condition_id) -> PairPosition | None` | `self._positions.get(condition_id)` |
| `sync_position` | `(condition_id) -> PairPosition` | Fetch `get_onchain_balance(yes_token_id)` and `get_onchain_balance(no_token_id)`, update the `PairPosition` yes/no balance fields. Preserve avg_entry and cost_basis (sync only updates balances). |
| `sync_all` | `() -> dict[str, PairPosition]` | `sync_position` for every registered condition_id. |
| `list_positions` | `() -> dict[str, PairPosition]` | Return `self._positions.copy()`. |
| `get_redeemable_positions` | `() -> list[PairPosition]` | Filter `_positions` where `is_resolved=True` and balance > 0 for winning outcome. |
| `mark_resolved` | `(condition_id, resolved_outcome) -> PairPosition` | Set `is_resolved=True` and `resolved_outcome`, return updated position. |

Split method:

```python
async def split(
    self, condition_id: str, amount: int, *, approve: bool = True
) -> SplitOperation:
```

1. `_require_position(condition_id)` — raise PairLifecycleError if missing.
2. Fetch `OnChainBalance` via `gateway.get_onchain_balance(yes_token_id)` (use either
   token; split costs USDC, not tokens).  Using USDC balance from
   `gateway.get_onchain_balance(yes_token_id).usdc_balance`.
3. Compare `usdc_balance * 1e6 >= amount`. Raise `InsufficientBalanceError` if not.
4. Optionally call `gateway.approve_usdc(amount)`.
5. Call `gateway.split(condition_id, amount)` → `SplitResult`.
6. Update position: both sides += `amount / 2 / 1e6`.  Cost basis += `amount / 2 / 1e6`
   per side.  Recompute avg_entry = cost_basis / balance (avoid div-by-zero).
7. Return `SplitOperation`.

Merge method:

```python
async def merge(
    self, condition_id: str, amount: int, *, approve: bool = True
) -> MergeOperation:
```

1. `_require_position(condition_id)`.
2. Fetch both token balances.
3. Check both balances >= `amount / 1e6`. Raise `InsufficientBalanceError` if not.
4. Call `gateway.merge(condition_id, amount)` → `MergeResult`.
5. Compute proceeds = `amount / 1e6` (one USDC per pair).
6. Update position: decrement both balances by `amount / 1e6`.  Prorate cost basis:
   `cost_basis *= (new_balance / old_balance)`.  Recompute avg_entry.
7. Return `MergeOperation`.

Redeem method:

```python
async def redeem(
    self, condition_id: str, index_set: int | None = None
) -> RedeemOperation:
```

1. `_require_position(condition_id)`.
2. Raise `PairLifecycleError("Market not resolved")` if not resolved.
3. Resolve `outcome_index`: 0 for "YES", 1 for "NO", or from `index_set` param.
4. Winning-side balance = `yes_balance if outcome == "YES" else no_balance`.
5. Raise `PairLifecycleError("No winning tokens to redeem")` if balance ≈ 0.
6. Call `gateway.redeem(condition_id, outcome_index, int(winning_balance * 1e6))`.
7. Zero the winning side's balance and cost basis.
8. Return `RedeemOperation`.

Sell remainder method:

```python
async def sell_remainder(
    self, market_id: str, outcome: str
) -> SellRemainderOperation:
```

1. Resolve `condition_id` via `_market_to_condition`.
2. Get `PairPosition`.
3. Determine token balance for the outcome.  If smaller than a threshold
   (e.g. `1e-3`), return `SellRemainderOperation(orders_placed=0)`.
4. If `self._executor` is None, raise `PairLifecycleError("No executor configured")`.
5. Create an `OrderIntent`:
   - `side=OrderSide.SELL`, `outcome=outcome`, `size=balance`,
     `price=sell_price`, `time_in_force=TimeInForce.IOC`,
     `reduce_only=True`.
6. Submit via `self._executor.execute(StrategyIntent(...))`.
7. Return `SellRemainderOperation` with the fill amount (from the result).

One-sided halt method:

```python
async def one_sided_halt(
    self, market_id: str, outcome: str
) -> OneSidedHaltResult:
```

1. Cancel all open orders for the given outcome side by delegating to
   `IntentExecutor.cancel_all(...)` or by emitting a `CancelIntent` with
   `market_id` and outcome filter.
2. Record that side is halted (in-memory set: `_halted_sides: set[tuple[str, str]]`).
3. Return `OneSidedHaltResult`.

Internal helpers:

```python
def _require_position(self, condition_id: str) -> PairPosition:
    pos = self._positions.get(condition_id)
    if pos is None:
        raise PairLifecycleError(f"Condition {condition_id} not registered")
    return pos
```

**1d. Wire into polymarket `__init__.py` (separate task, see Task 3)**

---

### Task 2: Unit tests

**File:** `tests/polymarket/test_pair_lifecycle.py`

Test class `TestPairLifecycleManager` with the following tests.  Use a
`MockContractsGateway` that returns canned balances and records calls, and a
`MockExecutor` for sell-remainder tests.  The mock gateway follows the
`ContractsGateway` interface but never touches a real chain.

Test scenarios:

| # | Test name | What it covers |
|---|---|---|
| 1 | `test_register_market` | Register a condition, verify position fields |
| 2 | `test_register_duplicate` | Registration of same condition_id raises PairLifecycleError |
| 3 | `test_get_position_nonexistent` | Returns None for unknown condition |
| 4 | `test_get_position_existing` | Returns the tracked PairPosition |
| 5 | `test_split_success` | Split 100 USDC (1e8 in 6-dec), verify updated position balances and cost basis |
| 6 | `test_split_insufficient_usdc` | Mock gateway reports low USDC; expect InsufficientBalanceError |
| 7 | `test_split_unregistered` | Split on unknown condition raises PairLifecycleError |
| 8 | `test_merge_success` | Merge 50 pairs (5e7 6-dec), verify position decremented, proceeds calculated |
| 9 | `test_merge_insufficient_balance` | Either side low → InsufficientBalanceError |
| 10 | `test_redeem_success` | Mark resolved (YES), redeem winning tokens, verify position zeroed |
| 11 | `test_redeem_unresolved` | Redeem on unresolved position → PairLifecycleError |
| 12 | `test_redeem_zero_balance` | Resolved but winning balance is zero → PairLifecycleError |
| 13 | `test_sell_remainder_small_balance` | Balance below threshold → no orders |
| 14 | `test_sell_remainder_with_executor` | Balance above threshold with executor → SellRemainderOperation with orders_placed > 0 |
| 15 | `test_sell_remainder_no_executor` | No executor configured → PairLifecycleError |
| 16 | `test_sync_position` | sync_position reads fresh balances and updates yes/no_balance fields |
| 17 | `test_sync_all` | sync_all refreshes all registered positions |
| 18 | `test_list_positions` | Returns all registered positions |
| 19 | `test_get_redeemable_positions` | Only resolved markets with winning balance > 0 appear in redeemable list |
| 20 | `test_mark_resolved` | mark_resolved sets is_resolved and resolved_outcome |
| 21 | `test_one_sided_halt` | Halts quoting for a given outcome, records halted sides |
| 22 | `test_one_sided_halt_unregistered` | Halt on unregistered market → PairLifecycleError |

---

### Task 3: Wire into polymarket `__init__.py`

**File:** `polymind/polymarket/__init__.py`

Add imports for all new types:

```python
from polymind.polymarket.pair_lifecycle import (
    MergeOperation,
    OneSidedHaltResult,
    PairLifecycleManager,
    PairPosition,
    RedeemOperation,
    SellRemainderOperation,
    SplitOperation,
)
```

Append to `__all__`:

```python
    "PairLifecycleManager",
    "PairPosition",
    "SplitOperation",
    "MergeOperation",
    "RedeemOperation",
    "SellRemainderOperation",
    "OneSidedHaltResult",
```

**File:** `polymind/polymarket/errors.py`

Append the two new error classes after the existing `InsufficientGasError`:

```python
class InsufficientBalanceError(PolymarketError):
    """Insufficient token or USDC balance for the requested operation."""
    ...

class PairLifecycleError(PolymarketError):
    """Invalid pair-lifecycle operation (e.g. redeem on unresolved market)."""
    ...
```

Also export them from `polymarkets/__init__.py`:

```python
from polymind.polymarket.errors import (
    InsufficientBalanceError,
    PairLifecycleError,
    ...
)
```

---

### Task 4: Integration test connecting PairLifecycleManager + ContractsGateway

**File:** `tests/polymarket/test_pair_lifecycle_integration.py`

Integration test that exercises the full stack end-to-end (using mocked chain
calls — no real RPC).  The test constructs a `ContractsGateway` with a
`ContractsConfig` that points at a local Anvil fork or uses `asyncio.to_thread`
patches to intercept Web3 calls.

Test scenarios:

1. **`test_register_then_split`**: Register a market, call `split()` via
   `PairLifecycleManager`, verify the `ContractsGateway` received the correct
   parameters and returned a result, and that the `PairPosition` was updated.

2. **`test_register_then_merge`**: Same flow for merge.

3. **`test_register_mark_resolved_then_redeem`**: Full lifecycle: register →
   split → mark_resolved → redeem.  Verify position is zeroed after redemption.

4. **`test_sync_from_gateway`**: Change the mock gateway's balance between
   calls and verify `sync_position` picks up the new balance.

5. **`test_pair_workflow_via_runner`**: Create a `WorkflowRunner` configured
   with a `PairLifecycleManager`.  Send a `WorkflowCommand(SPLIT, ...)` and
   verify the runner delegates to the manager and returns a successful
   `CommandResult`.

---

### Task 5: Run full test suite

Commands:

```
python -m pytest tests/polymarket/test_pair_lifecycle.py -v
python -m pytest tests/polymarket/test_pair_lifecycle_integration.py -v
python -m pytest tests/ -x --timeout=30 -q
```

Expected outcomes:
- All 22 unit tests pass.
- All 5 integration tests pass.
- Zero regressions in the full suite (existing 211+ tests).
