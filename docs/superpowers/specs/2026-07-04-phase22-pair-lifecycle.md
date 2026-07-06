> **Status:** Superseded by [`docs/architecture.md`](../../architecture.md) and [`docs/architecture/decisions/`](../../architecture/decisions/). This spec was a design document and is kept for historical reference only.

# Phase 22: PairLifecycleManager — Design

**Status:** Design
**Date:** 2026-07-04

## Overview

A `PairLifecycleManager` that tracks YES/NO token inventory for every registered
market and provides higher-level pair lifecycle operations — split, merge, redeem,
sell remainder, and one-sided halt. The manager wraps `ContractsGateway` for
on-chain execution but adds an inventory-tracking layer, balance pre-checks, and
state awareness (market resolution, redemption readiness).

The manager is referenced in the `WorkflowRunner` as the delegate for pair
lifecycle commands (`SPLIT`, `MERGE`, `REDEEM`, `SELL_REMAINDER`,
`ONE_SIDED_HALT`). Workflow state machines (Rebate, Event MM, Sniper, Copy
Trade) never call the manager directly; they emit `WorkflowCommand` instances and
the runner dispatches to the manager.

## Existing contracts

### `polymind/core/workflows.py` — `WorkflowCommand`, `CommandType`

```
CommandType:
  START, STOP, PAUSE, RESUME, RESTART          (lifecycle)
  SPLIT, MERGE, REDEEM, SELL_REMAINDER, ONE_SIDED_HALT  (pair lifecycle)

WorkflowCommand:
  workflow_id: str
  command: CommandType
  reason: str = ""
  params: dict[str, Any]
  timestamp: datetime
```

The params dict carries pair-operation arguments:

| Command | Required params |
|---|---|
| SPLIT | `condition_id`, `amount` |
| MERGE | `condition_id`, `amount` |
| REDEEM | `condition_id`, `index_set` (optional) |
| SELL_REMAINDER | `market_id`, `outcome` |
| ONE_SIDED_HALT | `market_id`, `outcome` |

### `polymind/polymarket/contracts.py` — `ContractsGateway`

The gateway provides low-level on-chain methods. The manager calls these but
adds pre/post logic:

```
split(condition_id, amount, outcomes=None) -> SplitResult
merge(condition_id, amount, outcomes=None) -> MergeResult
redeem(condition_id, outcome_index, amount) -> RedeemResult
get_onchain_balance(token_id) -> OnChainBalance
approve_usdc(amount) -> TransactionResult
approve_exchange(token_id, amount) -> TransactionResult
```

ContractsGateway domain types (`SplitResult`, `MergeResult`, `RedeemResult`,
`OnChainBalance`, `TransactionResult`) are re-exposed or mapped by the manager.
The manager never replaces them; it enriches them with inventory context.

### `polymind/workflows/runner.py` — `WorkflowRunner`

`WorkflowRunner._handle_existing` routes pair commands through
`PAIR_COMMAND_MAP` (`SPLIT`/`MERGE` -> `MERGE_DONE`, `REDEEM` -> `REDEEM_DONE`).
In Phase 22 the runner is extended so that before transitioning the state
machine, it invokes `PairLifecycleManager.<method>()` to execute the on-chain
operation, then passes the result back to the state machine via the event.

### Error hierarchy (`polymind/polymarket/errors.py`)

The manager raises the same errors as ContractsGateway:
- `ContractError` — on-chain failure
- `InsufficientGasError` — no MATIC for gas
- `InsufficientBalanceError` (new, in errors.py) — insufficient YES/NO tokens for
  the requested operation

## Design

### 1. PairPosition — inventory snapshot

```python
@dataclass
class PairPosition:
    """Snapshot of YES/NO token inventory for a single condition."""

    condition_id: str
    yes_token_id: str
    no_token_id: str
    yes_balance: float       # current YES tokens held
    no_balance: float        # current NO tokens held
    yes_avg_entry: float     # average entry price for YES (USDC per token)
    no_avg_entry: float      # average entry price for NO
    yes_cost_basis: float    # total USDC spent acquiring YES tokens
    no_cost_basis: float     # total USDC spent acquiring NO tokens
    is_resolved: bool        # True once market resolution is detected
    resolved_outcome: str | None = None  # "YES", "NO", or None
```

Positions are tracked per `condition_id`. The manager maintains an internal
`dict[str, PairPosition]` that is updated on every split, merge, or external
sync call.

Positions are **not** persisted across restarts — they are rebuilt from
on-chain balances on startup via `sync_position(condition_id)`.

### 2. Operation result types

```python
@dataclass
class SplitOperation:
    """Result of splitting USDC into YES + NO tokens."""

    condition_id: str
    usdc_amount: float       # USDC consumed (6-dec)
    yes_amount: float        # YES tokens received
    no_amount: float         # NO tokens received
    tx_hash: str
    updated_position: PairPosition  # position after the split


@dataclass
class MergeOperation:
    """Result of merging YES + NO tokens back into USDC."""

    condition_id: str
    outcome_token_amount: float  # number of outcome-token pairs merged
    proceeds_usdc: float         # USDC received (approximate)
    tx_hash: str
    updated_position: PairPosition  # position after the merge


@dataclass
class RedeemOperation:
    """Result of redeeming winning tokens after resolution."""

    condition_id: str
    outcome: str                 # the winning outcome ("YES" or "NO")
    amount_redeemed: float       # number of tokens redeemed
    proceeds_usdc: float         # USDC received
    tx_hash: str
    updated_position: PairPosition  # position after redemption (zeroed)


@dataclass
class SellRemainderOperation:
    """Result of selling remainder tokens on the CLOB."""

    market_id: str
    outcome: str
    amount_sold: float
    proceeds_usdc: float
    orders_placed: int           # number of CLOB orders placed


@dataclass
class OneSidedHaltResult:
    """Result of halting one side of a pair's quoting."""

    market_id: str
    outcome: str                 # the side that was halted
    orders_cancelled: int        # number of cancelled open orders
```

### 3. PairLifecycleManager class

Location: `polymind/polymarket/pair_lifecycle.py`

```python
class PairLifecycleManager:
    """YES/NO token inventory tracker and pair-lifecycle executor.

    Wraps ``ContractsGateway`` with an inventory-tracking layer so that
    higher-level callers (WorkflowRunner, state machines) can issue split,
    merge, redeem, sell-remainder, and one-sided-halt commands without
    managing token IDs or checking balances manually.
    """

    def __init__(self, gateway: ContractsGateway, ...):
        self._gateway = gateway
        self._positions: dict[str, PairPosition] = {}
        self._token_id_to_condition: dict[str, str] = {}
```

#### 3a. Inventory API

```
register_market(condition_id, yes_token_id, no_token_id, initial_yes=0, initial_no=0)
    -> PairPosition
    Register a market for inventory tracking.  Creates a PairPosition entry.
    Raises PairLifecycleError if condition_id already registered.

get_position(condition_id) -> PairPosition | None
    Return the current tracked position, or None if not registered.

sync_position(condition_id) -> PairPosition
    Re-read on-chain balances via ContractsGateway.get_onchain_balance for both
    token IDs and update the in-memory PairPosition.  Returns the updated position.

sync_all() -> dict[str, PairPosition]
    Call sync_position for every registered condition_id.

list_positions() -> dict[str, PairPosition]
    Return all registered positions.

get_redeemable_positions() -> list[PairPosition]
    Return all positions where is_resolved=True and balance > 0 for the
    winning outcome.
```

#### 3b. Split

```
async split(condition_id, amount, approve=True) -> SplitOperation

Flow:
1. Load PairPosition; raise PairLifecycleError if not registered.
2. Check on-chain USDC balance >= amount (6-dec).
   Raise InsufficientBalanceError if insufficient.
3. If approve: call gateway.approve_usdc(amount) first.
4. Call gateway.split(condition_id, amount).
5. Update PairPosition:
   - yes_balance += amount/2   (split produces equal YES and NO)
   - no_balance  += amount/2
   - yes_cost_basis += amount / 2   (cost basis: half the USDC went to YES)
   - no_cost_basis  += amount / 2
   - Recompute avg_entry = cost_basis / balance for each side.
   - (In reality the cost basis attribution depends on secondary-market
      prices; the linear 50/50 split is a ceiling.  This is documented.)
6. Return SplitOperation with updated position.
```

#### 3c. Merge

```
async merge(condition_id, amount, approve=True) -> MergeOperation

Flow:
1. Load PairPosition; raise if not registered.
2. Determine token_id for the merge side.  The contract merge burns
   equal amounts of both YES and NO.  amount is the number of token
   *pairs* to merge.
3. Check on-chain balance for both YES and NO token IDs >= amount.
   Raise InsufficientBalanceError if either is insufficient.
4. Call gateway.merge(condition_id, amount).
5. Compute approximate proceeds:
   - proceeds_usdc = amount * 1.0  (each merged pair returns 1 USDC
     minus fees; 1.0 is the ceiling / ideal-case approximation).
6. Update PairPosition:
   - yes_balance -= amount
   - no_balance  -= amount
   - Prorate cost basis: reduce each side by (amount / previous_balance * cost_basis)
   - Recompute avg_entry.
7. Return MergeOperation.
```

#### 3d. Redeem

```
async redeem(condition_id, index_set=None) -> RedeemOperation

Flow:
1. Load PairPosition; raise if not registered.
2. Raise PairLifecycleError if not resolved or no winning-outcome balance.
3. Determine outcome_index from resolved_outcome ("YES" -> 0, "NO" -> 1,
   or from index_set param).
4. Determine the winning token balance.
5. Call gateway.redeem(condition_id, outcome_index, amount).
6. Update PairPosition:
   - Zero the winning-side balance and cost basis.
   - Mark proceeds received.
7. Return RedeemOperation.
```

#### 3e. Sell remainder

```
async sell_remainder(market_id, outcome) -> SellRemainderOperation

Flow:
1. Resolve market_id -> condition_id via internal map.
2. Load PairPosition.
3. Determine token balance for the outcome to sell.
4. If balance <= threshold (e.g. 0.001), return empty SellRemainderOperation.
5. Create a CLOB sell order for the remainder tokens at a competitive
   price (e.g. 0.5 for unresolved, 0.99 for resolved YES, etc.).
6. Return SellRemainderOperation with order count.

Note: This method is a thin wrapper that creates a CLOB order via the
order-execution pipeline (IntentExecutor).  It does **not** execute
the trade itself — it emits an OrderIntent through the standard path.
```

#### 3f. One-sided halt

```
async one_sided_halt(market_id, outcome) -> OneSidedHaltResult

Flow:
1. Resolve market_id -> condition_id.
2. Cancel all open CLOB orders for the given outcome side.
3. Record that quoting is suspended for that side.
4. Return OneSidedHaltResult.

This is a quoting-level operation — it does not touch on-chain balances.
It delegates to IntentExecutor.cancel_all(market_id, outcome=...).
```

### 4. Market resolution detection

The manager does **not** poll for resolution. Instead it exposes:

```
mark_resolved(condition_id, resolved_outcome) -> PairPosition
```

that external code (fill processor, WebSocket resolution handler) calls when
a market resolution event arrives.  After marking resolved, the position
appears in `get_redeemable_positions()`.

### 5. Composability with WorkflowRunner

In `WorkflowRunner`, the `process_command` method for pair commands becomes:

```
if cmd.command in {SPLIT, MERGE, REDEEM, SELL_REMAINDER, ONE_SIDED_HALT}:
    return await self._handle_pair_command(cmd)
```

`_handle_pair_command`:

1. Looks up the workflow instance to verify it exists and is active.
2. Delegates to `self._pair_lifecycle.<method>(**cmd.params)`.
3. On success, transitions the state machine with the corresponding event
   (MERGE_DONE, REDEEM_DONE).
4. On failure, returns `CommandResult(success=False, message=str(exc))`.

The runner receives the `PairLifecycleManager` in its constructor:

```
class WorkflowRunner:
    def __init__(self, registry=None, pair_lifecycle=None):
        ...
        self._pair_lifecycle = pair_lifecycle or PairLifecycleManager(...)
```

### 6. Balance checking

Before any on-chain split, the manager calls
`ContractsGateway.get_onchain_balance(token_id)` to confirm the account
has sufficient funds.  This catches the common "forgot to deposit USDC"
mistake before paying gas for a revert.

New error class added to `polymind/polymarket/errors.py`:

```python
class InsufficientBalanceError(PolymarketError):
    """Insufficient token or USDC balance for the requested operation."""
    ...
```

### 7. Token ID mapping

The manager maintains a bidirectional map:
- `_positions: dict[condition_id, PairPosition]`
- `_token_id_to_condition: dict[token_id, condition_id]`

This allows lookups by either key, which is needed because `FillEvent`
carries `market_id` and `outcome` (not `condition_id`), while the
contracts operate on `condition_id`.

The mapping from `(market_id, outcome)` to `token_id` is provided by the
Data API (`PolymarketDataAPI.get_market()` returns `clobTokenIds`).  The
manager accepts a pre-built map via `register_market()`.

## Error handling

| Scenario | Error |
|---|---|
| Operation on unregistered condition | `PairLifecycleError("Market not registered")` |
| Insufficient USDC for split | `InsufficientBalanceError("USDC balance X < Y required")` |
| Insufficient tokens for merge | `InsufficientBalanceError("YES balance X < Y required")` |
| Redeem on unresolved market | `PairLifecycleError("Market not resolved")` |
| Redeem on zero-winning balance | `PairLifecycleError("No winning tokens to redeem")` |
| On-chain transaction failure | `ContractError` (from ContractsGateway) |
| Invalid outcome string | `PairLifecycleError("Invalid outcome: ...")` |

## Non-goals

- **Persistence**: Position state is in-memory only.  Sync from chain on
  restart.
- **Order execution**: Sell-remainder emits intents but does **not** manage
  order lifecycle.  The executor layer owns matching and fill tracking.
- **Gas estimation**: The manager uses the gas limit from `ContractsConfig`.
  Dynamic gas estimation is a future concern.
- **Multi-account**: The manager tracks one wallet's inventory (the one
  configured in `ContractsConfig`).  Multi-account support would require
  multiple manager instances or a shim layer.
