> **Status:** Superseded by [`docs/architecture.md`](../../architecture.md) and [`docs/architecture/decisions/`](../../architecture/decisions/). This spec was a design document and is kept for historical reference only.

# Phase 23: MakerRebateStrategy — Design

**Status:** Design
**Date:** 2026-07-04
**ADR:** ADR 0002 (Strategies emit intents; executors place orders)
**Workflow State Machine:** `polymind/workflows/maker_rebate/state_machine.py`
**Runner:** `polymind/workflows/runner.py`
**Pair Lifecycle:** `polymind/polymarket/pair_lifecycle.py`

## 1. Overview

A `MakerRebateStrategy` that detects and captures the **maker rebate arbitrage**
on CLOB prediction markets: when `YES_price + NO_price < 1`, buying both sides
at a combined discount and (after fills) merging them back to USDC yields a
risk-free profit.

The strategy is a **bounded component** of the broader Maker Rebate workflow
(per Phase 5 architecture: `docs/architecture.md` lines 422-425). It owns the
tick-level pricing and intent production; the workflow state machine
(`RebateStateMachine`) and `WorkflowRunner` own the post-fill lifecycle —
merge, redeem, error recovery.

**Key constraint:** This is a pair-level strategy. Unlike `ClassicMMStrategy`
or `AMMStrategy` which analyze a single market outcome, `MakerRebateStrategy`
must consume both YES and NO market snapshots for a given condition and make
a joint pricing decision.

### 1a. The Rebate Opportunity

For a binary market with YES and NO outcome tokens:

```
rebate_spread = 1.0 - (YES_mid_price + NO_mid_price)
```

When `rebate_spread > min_spread + fees`, the strategy:

1. Places **buy** limit orders for YES at `YES_bid * (1 - buffer_pct)`
2. Places **buy** limit orders for NO at `NO_bid * (1 - buffer_pct)`
3. Waits for both orders to fill (tracked externally via fill events)
4. After both fills are detected, the workflow state machine transitions to
   `FILLS_COMPLETE`, then a **merge** command is issued (via
   `PairLifecycleManager.merge()`) to convert the paired YES+NO tokens back
   to USDC, locking in the spread.
5. If the market has resolved before merging, the workflow can go directly to
   **redeem** instead.

Profit = `(1.0 - yes_price - no_price) * position_size - fees`

Since merge returns ~1 USDC per pair (minus the CLOB's small redeeming fee),
the captured spread is essentially guaranteed once both sides fill at prices
summing to less than 1.

## 2. Package Layout

```
polymind/strategies/market_making/maker_rebate/
├── __init__.py          # existing; update exports
├── pair_snapshot.py     # PairSnapshot dataclass
├── pricing.py           # Rebate opportunity detection + spread math
├── sizing.py            # Position sizing for paired buy orders
└── strategy.py          # MakerRebateStrategy (extends BaseMMStrategy)
```

## 3. Components

### 3.1 PairSnapshot — combined YES/NO market view

Location: `polymind/strategies/market_making/maker_rebate/pair_snapshot.py`

```python
@dataclass
class PairSnapshot:
    """Combined snapshot of both YES and NO markets for one condition.

    Carries the individual MarketSnapshot objects for each side plus
    derived pair-level fields.
    """

    condition_id: str
    yes_market_id: str
    no_market_id: str
    timestamp: datetime

    # YES side
    yes_bid: float
    yes_ask: float
    yes_mid: float

    # NO side
    no_bid: float
    no_ask: float
    no_mid: float

    # Derived pair fields (computed at construction)
    combined_mid: float        # yes_mid + no_mid
    rebate_spread: float       # 1.0 - combined_mid
    implicit_risk_free: float  # 1.0 - combined_ask (for taker scenarios)
```

Derived fields are computed in `__post_init__`:

```python
def __post_init__(self) -> None:
    self.combined_mid = round(self.yes_mid + self.no_mid, 6)
    self.rebate_spread = round(1.0 - self.combined_mid, 6)
    self.implicit_risk_free = round(1.0 - (self.yes_ask + self.no_ask), 6)
```

A factory function `from_snapshots(yes_snapshot, no_snapshot, condition_id)`
constructs a `PairSnapshot` from two `MarketSnapshot` objects (from
`polymind.execution.fill_model`).

### 3.2 Pricing — rebate opportunity analysis

Location: `polymind/strategies/market_making/maker_rebate/pricing.py`

```python
@dataclass
class RebatePricingConfig:
    """Configuration for rebate opportunity detection."""

    min_rebate_spread: float = 0.005   # 0.5 % minimum rebate to trade (excl. fees)
    fee_buffer: float = 0.001          # additional buffer for maker fees (0.1 %)
    price_buffer_pct: float = 0.002    # how far behind bid to place for fill priority
```

**Core function — `detect_rebate_opportunity`:**

```python
def detect_rebate_opportunity(
    pair: PairSnapshot,
    config: RebatePricingConfig,
) -> tuple[float, float, float] | None:
    """Check if a profitable rebate exists.

    Returns (yes_buy_price, no_buy_price, expected_spread) if the
    opportunity is viable, else None.

    The effective bid prices are:
      yes_price = pair.yes_bid * (1 - price_buffer_pct)
      no_price  = pair.no_bid  * (1 - price_buffer_pct)

    The expected captured spread is:
      captured = 1.0 - yes_price - no_price - (2 * fee_buffer)

    Trade only if captured >= min_rebate_spread.
    """
```

The buffer behind the bid ensures the passive limit order is slightly more
aggressive than the current best bid, improving fill probability without
crossing the spread to the ask (which would eliminate the rebate).

**Edge case — one-sided liquidity:**

If either side has `bid_size == 0` (no bid), the opportunity is skipped
entirely. A zero-bid market cannot be filled passively.

### 3.3 Sizing — pair position sizing

Location: `polymind/strategies/market_making/maker_rebate/sizing.py`

```python
@dataclass
class RebateSizingConfig:
    """Configuration for paired buy-order sizing."""

    max_exposure_usdc: float = 100.0      # max USDC committed per condition
    min_order_size: float = 10.0           # minimum order size per side
    max_order_size: float = 500.0          # maximum order size per side
    use_debt_ceiling: bool = True          # cap total open exposure across conditions
    max_total_exposure_usdc: float = 5000.0  # aggregate cap across all active rebates
```

**Core function — `compute_pair_sizes`:**

```python
def compute_pair_sizes(
    pair: PairSnapshot,
    config: RebateSizingConfig,
    current_exposure: float,        # current USDC committed to this condition
    total_exposure: float,          # total USDC committed across all conditions
) -> tuple[float, float] | None:
    """Determine YES and NO order sizes for this pair.

    The two sides always receive equal sizes (the merge requires
    equal YES and NO token amounts).  Returns (yes_size, no_size)
    or None if the opportunity should be skipped entirely.

    Constraints:
    1. yes_size == no_size  (merge invariant)
    2. yes_price * yes_size + no_price * no_size <= max_exposure_usdc
    3. total_exposure + (yes_price * yes_size + no_price * no_size)
       <= max_total_exposure_usdc
    4. yes_size in [min_order_size, max_order_size]
    """
```

The equal-size invariant is critical: the `PairLifecycleManager.merge()`
call burns equal amounts of YES and NO tokens, and the CLOB's redeem/merge
contract requires matched pairs. An unmatched position creates a "remainder"
that must be sold separately or held to resolution.

### 3.4 Strategy — MakerRebateStrategy

Location: `polymind/strategies/market_making/maker_rebate/strategy.py`

```python
@register("maker_rebate")
class MakerRebateStrategy(BaseMMStrategy):
    """Captures rebate spread by buying YES and NO when their sum < 1.

    Produces paired buy OrderIntents for both sides of a condition.
    Post-fill lifecycle (merge, redeem) is owned by the WorkflowRunner
    and RebateStateMachine; this strategy only produces intents.
    """

    def __init__(
        self,
        pricing_config: RebatePricingConfig | None = None,
        sizing_config: RebateSizingConfig | None = None,
        config: StrategyConfig | None = None,
        pair_lifecycle: PairLifecycleManager | None = None,
    ):
        super().__init__(config)
        self.pricing_config = pricing_config or RebatePricingConfig()
        self.sizing_config = sizing_config or RebateSizingConfig()
        self._pair_lifecycle = pair_lifecycle
        self._active_conditions: dict[str, RebateState] = {}  # condition_id -> state
```

**`analyze` method:**

The `analyze` signature uses `market: Any` per `BaseMMStrategy`. The
`MakerRebateStrategy` expects a `PairSnapshot`:

```python
async def analyze(self, market: Any) -> StrategyIntent | None:
    """Analyze a pair snapshot and produce buy intents for both sides.

    Parameters
    ----------
    market : PairSnapshot
        A combined YES/NO snapshot (not a single MarketSnapshot).

    Returns
    -------
    StrategyIntent | None
        Contains two OrderIntent (buy YES, buy NO) and one CancelIntent
        to clear stale orders for both markets.  Returns None when no
        rebate opportunity exists.
    """
    if not isinstance(market, PairSnapshot):
        raise TypeError(f"MakerRebateStrategy expects PairSnapshot, got {type(market)}")

    # Skip if we already have open orders for this condition
    cond_id = market.condition_id
    if cond_id in self._active_conditions:
        return None  # let existing orders fill; don't churn

    # Detect opportunity
    prices = detect_rebate_opportunity(market, self.pricing_config)
    if prices is None:
        return None

    yes_price, no_price, expected_spread = prices

    # Compute sizes
    current_exp = self._current_exposure(cond_id)
    total_exp = self._total_exposure()
    sizes = compute_pair_sizes(market, self.sizing_config, current_exp, total_exp)
    if sizes is None:
        return None

    yes_size, no_size = sizes

    now = datetime.now(timezone.utc)

    # Cancel stale orders for BOTH markets before placing new ones
    cancels = [
        CancelIntent(
            market_id=market.yes_market_id,
            reason=f"Maker rebate refresh @ {now.isoformat()}",
        ),
        CancelIntent(
            market_id=market.no_market_id,
            reason=f"Maker rebate refresh @ {now.isoformat()}",
        ),
    ]

    # Paired buy orders
    orders = [
        OrderIntent(
            market_id=market.yes_market_id,
            side=OrderSide.BUY,
            price=yes_price,
            size=yes_size,
            outcome="YES",
            time_in_force=TimeInForce.GTC,
            metadata={
                "condition_id": cond_id,
                "strategy": "maker_rebate",
                "expected_spread": expected_spread,
            },
        ),
        OrderIntent(
            market_id=market.no_market_id,
            side=OrderSide.BUY,
            price=no_price,
            size=no_size,
            outcome="NO",
            time_in_force=TimeInForce.GTC,
            metadata={
                "condition_id": cond_id,
                "strategy": "maker_rebate",
                "expected_spread": expected_spread,
            },
        ),
    ]

    # Track this condition as active
    self._active_conditions[cond_id] = RebateState.ORDERS_PLACED

    return StrategyIntent(
        timestamp=now,
        strategy_name=self.name,
        orders=orders,
        cancels=cancels,
        metadata={
            "condition_id": cond_id,
            "expected_spread": expected_spread,
        },
    )
```

**State tracking helper:**

```python
def mark_filled(self, condition_id: str) -> None:
    """Called externally when both YES and NO fills are confirmed.

    Removes the condition from active tracking so the next tick
    can detect a new opportunity.
    """
    self._active_conditions.pop(condition_id, None)

def _current_exposure(self, condition_id: str) -> float:
    """Return USDC exposure for a condition (via pair_lifecycle or local tracking)."""
    if self._pair_lifecycle is not None:
        pos = self._pair_lifecycle.get_position(condition_id)
        if pos is not None:
            return pos.yes_cost_basis + pos.no_cost_basis
    return 0.0

def _total_exposure(self) -> float:
    """Return total USDC exposure across all tracked conditions."""
    if self._pair_lifecycle is not None:
        total = 0.0
        for pos in self._pair_lifecycle.list_positions().values():
            total += pos.yes_cost_basis + pos.no_cost_basis
        return total
    return sum(0.0 for _ in self._active_conditions)  # fallback
```

## 4. Integration with WorkflowRunner and PairLifecycleManager

The `MakerRebateStrategy` is **not** directly coupled to the workflow state
machine. The integration boundary is:

```
Tick (PairSnapshot)
    │
    ▼
MakerRebateStrategy.analyze(pair) ───► StrategyIntent
    │                                        │
    ▼                                        ▼
IntentExecutor.execute(intent)        (order placement)
    │
    ▼
FillEvent (YES filled, NO filled)     (detected externally via WS)
    │
    ▼
WorkflowRunner.process_command(
    START + maker_rebate workflow     ───► RebateStateMachine: IDLE → PLACING_ORDERS
)
    │
    ▼
PairLifecycleManager.split()
    (split USDC → YES + NO)          ───► RebateStateMachine: PLACING_ORDERS → AWAITING_FILLS
    │
    ▼
[Wait for fills via FillProcessor]
    │
    ▼
WorkflowRunner.process_command(
    MERGE command                     ───► PairLifecycleManager.merge()
                                         RebateStateMachine: AWAITING_FILLS → FILLS_COMPLETE
                                                              FILLS_COMPLETE → MERGING
)
    │
    ▼
[If resolved:]
WorkflowRunner.process_command(
    REDEEM command                    ───► PairLifecycleManager.redeem()
                                         RebateStateMachine: MERGING → REDEEMING → COMPLETED
)
```

**Key design choice:** The strategy only produces intents. The workflow
state machine and runner own the lifecycle after fills. The caller
(orchestrator / tick engine) is responsible for:

1. Constructing `PairSnapshot` from two `MarketSnapshot` objects before
   calling `analyze()`.
2. Feeding fill events back to the strategy (`mark_filled()`).
3. Routing lifecycle events to the `WorkflowRunner`.

This keeps the strategy testable from pair snapshots alone and avoids
coupling strategy logic to on-chain operations.

### 4a. PairSnapshot construction

The orchestrator builds `PairSnapshot` from two `MarketSnapshot` objects:

```python
def build_pair_snapshot(
    yes_snapshot: MarketSnapshot,
    no_snapshot: MarketSnapshot,
    condition_id: str,
) -> PairSnapshot:
    """Build a PairSnapshot from individual YES and NO snapshots."""
    return PairSnapshot(
        condition_id=condition_id,
        yes_market_id=yes_snapshot.market_id,
        no_market_id=no_snapshot.market_id,
        timestamp=yes_snapshot.timestamp,
        yes_bid=yes_snapshot.bid_price,
        yes_ask=yes_snapshot.ask_price,
        yes_mid=yes_snapshot.mid_price,
        no_bid=no_snapshot.bid_price,
        no_ask=no_snapshot.ask_price,
        no_mid=no_snapshot.mid_price,
    )
```

The orchestrator obtains `condition_id` via `PairLifecycleManager`'s
`_market_to_condition` mapping, or from the Data API's event/market
relationships.

### 4b. USDC balance check

Before the strategy can produce intents for a new condition, the orchestrator
should verify that the wallet has sufficient USDC to cover the split:

```
if token_bal.usdc_balance < yes_price * yes_size + no_price * no_size:
    skip condition (insufficient balance)
```

This check can be done by calling
`PairLifecycleManager._gateway.get_onchain_balance()` or by the strategy's
`_total_exposure()` returning a value near the configured debt ceiling.

A dedicated pre-trade check helper is provided:

```python
async def check_usdc_balance(
    pair_lifecycle: PairLifecycleManager,
    required_usdc: float,
) -> tuple[bool, float]:
    """Check USDC balance against the required amount.

    Returns (sufficient: bool, current_balance: float).
    """
    # Uses the first registered condition's USDC balance as proxy
    positions = pair_lifecycle.list_positions()
    if not positions:
        return False, 0.0
    first_cond = next(iter(positions))
    bal = await pair_lifecycle._gateway.get_onchain_balance(
        positions[first_cond].yes_token_id
    )
    return bal.usdc_balance >= required_usdc, bal.usdc_balance
```

## 5. Configuration

### 5.1 RebatePricingConfig

| Field | Type | Default | Description |
|---|---|---|---|
| `min_rebate_spread` | float | 0.005 | Minimum rebate spread to trade (excl. fees). 0.5 % |
| `fee_buffer` | float | 0.001 | Additional buffer for maker fees. 0.1 % |
| `price_buffer_pct` | float | 0.002 | How far behind bid to place orders for fill priority. 0.2 % |

### 5.2 RebateSizingConfig

| Field | Type | Default | Description |
|---|---|---|---|
| `max_exposure_usdc` | float | 100.0 | Max USDC per condition |
| `min_order_size` | float | 10.0 | Min order size per side |
| `max_order_size` | float | 500.0 | Max order size per side |
| `use_debt_ceiling` | bool | True | Cap total open exposure across conditions |
| `max_total_exposure_usdc` | float | 5000.0 | Aggregate cap across all active rebates |

## 6. Error Handling

| Scenario | Behaviour |
|---|---|
| `PairSnapshot` has missing bid on either side | Skip: `analyze()` returns `None` |
| USDC balance insufficient for split | Strategy produces intents but pre-trade check in orchestrator skips |
| Condition already has open orders | `analyze()` returns `None` (avoids duplicate placement) |
| `yes_price * yes_size` exceeds per-condition cap | `compute_pair_sizes` clamps to `max_exposure_usdc` |
| Combined exposure exceeds `max_total_exposure_usdc` | `compute_pair_sizes` returns `None` |
| Market resolves before merge | Workflow goes from `AWAITING_FILLS` → `FILLS_COMPLETE` → `REDEEMING` (skips merge) |
| One side fills but other does not | Remainder handling via `PairLifecycleManager.sell_remainder()` |
| Fee spike erases spread | `price_buffer_pct` + `fee_buffer` provide safety margin |
| Order placed but price moves | Standard cancel-and-replace on next tick |

### 6a. Fee-aware spread calculation

The effective captured spread accounts for both CLOB maker fees and the
redeem/merge fee:

```
effective_spread = 1.0 - yes_price - no_price - maker_fee_rate - merge_fee_rate
```

Where:
- `maker_fee_rate` = fee paid when the buy order fills (maker rebate may
  offset some or all of this)
- `merge_fee_rate` = fee paid when merging paired tokens back to USDC
  (typically small, ~0.1 % per pair)

The configurable `fee_buffer` field covers these costs. The strategy trades
only when:

```
1.0 - yes_price - no_price - 2 * fee_buffer >= min_rebate_spread
```

The factor of 2 accounts for worst-case fees on both the entry (maker fill)
and exit (merge) legs.

## 7. Edge Cases

### 7a. Partial fill on one side

If YES fills but NO does not, the condition is left with an unbalanced
position. The workflow should:

1. Keep the filled side's order open (don't cancel).
2. Wait for the other side to fill, possibly at a more aggressive price.
3. If the opportunity window closes, sell the excess remainder via
   `PairLifecycleManager.sell_remainder()` and accept a small loss.

The strategy handles this by leaving the condition in `_active_conditions`
until `mark_filled()` is called, preventing duplicate placement.

### 7b. Market resolution during order placement

If the market resolves while YES/NO orders are open:

1. Fill events stop (market is resolved, no more trading).
2. The winning side's order may still fill if it was already matched.
3. The workflow runner detects resolution via WebSocket event and calls
   `PairLifecycleManager.mark_resolved()`.
4. The workflow transitions directly to `REDEEMING`, skipping `MERGE`.

### 7c. Both sides fill but USDC merge fails

The merge transaction may revert due to:

- Insufficient approval (solved by the `approve=True` default in
  `PairLifecycleManager.merge()`).
- Insufficient MATIC for gas (catches via `InsufficientGasError`).
- Token pair mismatch (should not happen if strategy always buys equal
  amounts).

The workflow state machine transitions to `FAILED` on error, and the
operator can issue a `RESTART` after resolving the underlying issue.

### 7d. Fee rebate interaction

Polymarket's maker rebate program may rebate a portion of the maker fee
back to the trader. This improves the effective spread. The strategy's
`fee_buffer` can be tuned downward when maker rebate is active.

## 8. Non-goals

- **Order execution**: The strategy produces `StrategyIntent` only. The
  executor layer owns the CLOB transport, retry, and fill tracking.
- **Split/merge/redeem execution**: On-chain operations are owned by
  `PairLifecycleManager` via the `WorkflowRunner`.
- **Fill detection**: Fill events are detected externally (WebSocket) and
  routed to the strategy's `mark_filled()` method. The strategy does not
  poll for fills.
- **Multi-condition optimization**: The strategy treats each condition
  independently. Cross-condition exposure optimization is a future concern.
- **Taker orders**: The strategy is passive-only (limit orders at/behind
  the bid). Taker rebates (crossing the spread) are out of scope.

## 9. Future

- **Auto-tune `price_buffer_pct`** based on historical fill probability
  per condition.
- **Cross-condition debt ceiling** with priority ranking (most profitable
  spreads fill first).
- **Dynamic sizing** based on available USDC and opportunity quality
  (wider spreads get larger allocations).
- **Partial-fill resilience** with automated remainder management via
  `PairLifecycleManager.sell_remainder()`.
