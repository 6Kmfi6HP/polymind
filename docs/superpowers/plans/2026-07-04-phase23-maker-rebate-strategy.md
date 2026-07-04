# Phase 23: MakerRebateStrategy — Implementation Plan

**Date:** 2026-07-04

---

### Task 1: Create PairSnapshot dataclass

**File:** `polymind/strategies/market_making/maker_rebate/pair_snapshot.py`

New module defining `PairSnapshot` — a combined YES/NO market view for a single
condition.

```python
"""
Combined YES/NO pair snapshot for maker rebate analysis.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime


@dataclass
class PairSnapshot:
    """Combined snapshot of both YES and NO markets for one condition.

    Carries the individual MarketSnapshot data for each side plus
    derived pair-level fields computed at construction.
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

    # Derived pair fields (set in __post_init__)
    combined_mid: float = 0.0
    rebate_spread: float = 0.0
    implicit_risk_free: float = 0.0

    def __post_init__(self) -> None:
        self.combined_mid = round(self.yes_mid + self.no_mid, 6)
        self.rebate_spread = round(1.0 - self.combined_mid, 6)
        self.implicit_risk_free = round(1.0 - (self.yes_ask + self.no_ask), 6)


__all__ = ["PairSnapshot"]
```

**Edge cases in `__post_init__`:**
- If either mid is 0, `combined_mid` still computes correctly (may be <1).
- If either ask is 0, `implicit_risk_free` may be >1 (unusual but not prevented).
- All values are rounded to 6 decimal places (CLOB precision).

---

### Task 2: Create pricing module with rebate detection

**File:** `polymind/strategies/market_making/maker_rebate/pricing.py`

**2a. RebatePricingConfig dataclass:**

```python
@dataclass
class RebatePricingConfig:
    """Configuration for rebate opportunity detection."""

    min_rebate_spread: float = 0.005   # 0.5 % minimum rebate to trade (excl. fees)
    fee_buffer: float = 0.001          # additional buffer for maker fees (0.1 %)
    price_buffer_pct: float = 0.002    # how far behind bid to place orders
```

**2b. Core detection function:**

```python
def detect_rebate_opportunity(
    pair: PairSnapshot,
    config: RebatePricingConfig,
) -> tuple[float, float, float] | None:
    """Check if a profitable maker rebate opportunity exists.

    Parameters
    ----------
    pair:
        Combined snapshot for the condition.
    config:
        Pricing configuration.

    Returns
    -------
    (yes_buy_price, no_buy_price, expected_spread) or None.
    """
    # Skip if either side has no bid (no liquidity)
    if pair.yes_bid <= 0 or pair.no_bid <= 0:
        return None

    # Compute effective buy prices behind the bid
    yes_price = round(pair.yes_bid * (1.0 - config.price_buffer_pct), 6)
    no_price = round(pair.no_bid * (1.0 - config.price_buffer_pct), 6)

    # Expected captured spread after fees
    total_cost = yes_price + no_price
    captured_spread = round(1.0 - total_cost - 2.0 * config.fee_buffer, 6)

    if captured_spread < config.min_rebate_spread:
        return None

    return (yes_price, no_price, captured_spread)
```

**Unit-test scenarios:**

| Test | Input | Expected |
|---|---|---|
| YES=0.60, NO=0.35, bid exists | combined=0.95, spread=0.05 | returns (0.5988, 0.3493, ~0.0499) |
| YES=0.60, NO=0.40, no buffer | combined=1.00, spread=0.00 | returns (0.5988, 0.3992, ~0.001) < min → None |
| YES=0.55, NO=0.42 | combined=0.97, spread=0.03 | returns prices, spread >= 0.005 |
| YES=0.50, NO bid = 0 | one side has no bid | None |
| YES=0.60, NO=0.35, fee_buffer=0.02 | fees eat spread | captured < min → None |

---

### Task 3: Create sizing module for paired order sizes

**File:** `polymind/strategies/market_making/maker_rebate/sizing.py`

**3a. RebateSizingConfig dataclass:**

```python
@dataclass
class RebateSizingConfig:
    """Configuration for paired buy-order sizing."""

    max_exposure_usdc: float = 100.0
    min_order_size: float = 10.0
    max_order_size: float = 500.0
    use_debt_ceiling: bool = True
    max_total_exposure_usdc: float = 5000.0
```

**3b. Core sizing function:**

```python
def compute_pair_sizes(
    pair: PairSnapshot,
    config: RebateSizingConfig,
    yes_price: float,
    no_price: float,
    current_exposure: float = 0.0,
    total_exposure: float = 0.0,
) -> tuple[float, float] | None:
    """Determine equal YES and NO order sizes for a rebate opportunity.

    The two sides must be equal (merge invariant).  The function
    constrains the combined cost to not exceed per-condition and
    global exposure caps.

    Returns (yes_size, no_size) or None if the opportunity should
    be skipped.
    """
    # Start with max allowed per-side
    max_cost = config.max_exposure_usdc - current_exposure
    if max_cost <= 0:
        return None

    # Compute max equal size from cost cap
    combined_price = yes_price + no_price
    if combined_price <= 0:
        return None

    max_size_from_cost = max_cost / combined_price
    max_size = min(config.max_order_size, max_size_from_cost)

    # Check global debt ceiling
    if config.use_debt_ceiling:
        new_cost = max_size * combined_price
        if total_exposure + new_cost > config.max_total_exposure_usdc:
            # Clamp to available global headroom
            remaining_global = config.max_total_exposure_usdc - total_exposure
            max_size_from_global = remaining_global / combined_price
            max_size = min(max_size, max_size_from_global)
            if max_size < config.min_order_size:
                return None

    # Apply min_order_size floor
    if max_size < config.min_order_size:
        return None

    return (max_size, max_size)
```

**Unit-test scenarios:**

| Test | Input | Expected |
|---|---|---|
| max_exposure=100, combined_price=0.95 | size = 100/0.95 ≈ 105.26, clamped to max_order_size=100 | (100, 100) |
| max_exposure=100, current_exposure=90 | max_cost=10, size ≈ 10.53, min=10 | (10.53, 10.53) (rounded) |
| max_exposure=100, current_exposure=95 | max_cost=5, size ≈ 5.26, min=10 | None |
| global cap=1000, total_exp=950, combined=0.95 | remaining=50, size=52.63, max_order=500 | size=52.63 > min=10 → (52.63, 52.63) |
| global cap reached completely | remaining_global < min | None |
| zero combined price | guard returns None | None |

---

### Task 4: Create MakerRebateStrategy class

**File:** `polymind/strategies/market_making/maker_rebate/strategy.py`

New module implementing `MakerRebateStrategy`.  Follows the pattern of
`ClassicMMStrategy` and `AMMStrategy` but operates on `PairSnapshot` instead
of `MarketSnapshot`.

```python
"""
Maker Rebate market-making strategy: buys YES and NO when sum < 1.

Captures the rebate spread by placing paired limit buy orders on both
sides of a binary condition.  Post-fill lifecycle (merge, redeem) is
owned by the WorkflowRunner and RebateStateMachine.
"""

from __future__ import annotations

from datetime import datetime, timezone

from polymind.core.intents import CancelIntent, OrderIntent, OrderSide, StrategyIntent, TimeInForce
from polymind.core.strategy import BaseMMStrategy, StrategyConfig
from polymind.strategies.market_making.maker_rebate.pair_snapshot import PairSnapshot
from polymind.strategies.market_making.maker_rebate.pricing import (
    RebatePricingConfig,
    detect_rebate_opportunity,
)
from polymind.strategies.market_making.maker_rebate.sizing import (
    RebateSizingConfig,
    compute_pair_sizes,
)
from polymind.strategies import register


class RebateActivityState:
    """Internal state tracking for an active rebate attempt."""

    PENDING = "pending"
    ORDERS_PLACED = "orders_placed"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"


@register("maker_rebate")
class MakerRebateStrategy(BaseMMStrategy):
    """Captures rebate spread by buying YES and NO when sum < 1.

    Produces paired buy OrderIntents for both sides of a condition.
    Post-fill lifecycle (merge, redeem) is owned by the WorkflowRunner
    and RebateStateMachine; this strategy only produces intents.
    """

    def __init__(
        self,
        pricing_config: RebatePricingConfig | None = None,
        sizing_config: RebateSizingConfig | None = None,
        config: StrategyConfig | None = None,
    ):
        super().__init__(config)
        self.pricing_config = pricing_config or RebatePricingConfig()
        self.sizing_config = sizing_config or RebateSizingConfig()
        self._active_conditions: dict[str, str] = {}  # condition_id -> state

    async def analyze(self, market: PairSnapshot) -> StrategyIntent | None:
        """Analyze a PairSnapshot and produce paired buy intents.

        Parameters
        ----------
        market:
            A combined YES/NO pair snapshot.

        Returns
        -------
        StrategyIntent with paired buy orders, or None.
        """
        if not isinstance(market, PairSnapshot):
            raise TypeError(
                f"MakerRebateStrategy expects PairSnapshot, got {type(market).__name__}"
            )

        cond_id = market.condition_id

        # Skip if we already have open orders for this condition
        if cond_id in self._active_conditions:
            return None

        # Detect opportunity
        prices = detect_rebate_opportunity(market, self.pricing_config)
        if prices is None:
            return None

        yes_price, no_price, expected_spread = prices

        # Compute sizes (current/total exposure = 0 for first intent;
        # orchestrator manages the broader cap)
        sizes = compute_pair_sizes(
            market,
            self.sizing_config,
            yes_price=yes_price,
            no_price=no_price,
            current_exposure=0.0,
            total_exposure=0.0,
        )
        if sizes is None:
            return None

        yes_size, no_size = sizes
        now = datetime.now(timezone.utc)

        # Cancel stale orders for both markets
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

        # Track condition as active
        self._active_conditions[cond_id] = RebateActivityState.ORDERS_PLACED

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

    def mark_filled(self, condition_id: str) -> None:
        """Called externally when both YES and NO fills are confirmed.

        Removes the condition from active tracking so the next tick
        can detect a new opportunity.
        """
        self._active_conditions.pop(condition_id, None)

    def mark_partial_fill(self, condition_id: str, side: str) -> None:
        """Called externally when one side fills but not the other.

        Updates internal state so the strategy knows not to replace
        the partially-filled order.
        """
        if condition_id in self._active_conditions:
            self._active_conditions[condition_id] = RebateActivityState.PARTIALLY_FILLED

    def active_conditions(self) -> list[str]:
        """Return condition IDs currently being worked."""
        return list(self._active_conditions.keys())

    def reset(self) -> None:
        """Clear all active tracking (for restart/cleanup)."""
        self._active_conditions.clear()
```

**Design decisions:**
- Extends `BaseMMStrategy` via the `@register("maker_rebate")` decorator so it
  appears in the strategy registry automatically.
- `analyze()` accepts `PairSnapshot` (not `MarketSnapshot`). The type check in
  the first line catches misuse at runtime.
- The `_active_conditions` dict prevents duplicate order placement while fills
  are pending. The orchestrator calls `mark_filled()` when both Yes and No
  fills are detected.
- Two `CancelIntent` entries (one per market) ensure stale orders on either
  side are cleared before new ones are placed.

---

### Task 5: Update maker_rebate `__init__.py`

**File:** `polymind/strategies/market_making/maker_rebate/__init__.py`

Replace the current docstring-only file:

```python
"""
Maker Rebate MM — Y+N < $1 arbitrage + maker fee rebate.
"""

from polymind.strategies.market_making.maker_rebate.pair_snapshot import PairSnapshot
from polymind.strategies.market_making.maker_rebate.pricing import (
    RebatePricingConfig,
    detect_rebate_opportunity,
)
from polymind.strategies.market_making.maker_rebate.sizing import (
    RebateSizingConfig,
    compute_pair_sizes,
)
from polymind.strategies.market_making.maker_rebate.strategy import MakerRebateStrategy

__all__ = [
    "MakerRebateStrategy",
    "PairSnapshot",
    "RebatePricingConfig",
    "RebateSizingConfig",
    "compute_pair_sizes",
    "detect_rebate_opportunity",
]
```

---

### Task 6: Register strategy in built-in strategies

**File:** `polymind/strategies/__init__.py`

Update `register_builtin_strategies()` to include `MakerRebateStrategy`:

```python
def register_builtin_strategies() -> None:
    """Register all built-in strategies into PluginRegistry."""
    from polymind.strategies.market_making.amm import AMMStrategy
    from polymind.strategies.market_making.bands import BandsStrategy
    from polymind.strategies.market_making.classic_mm.strategy import ClassicMMStrategy
    from polymind.strategies.market_making.maker_rebate.strategy import MakerRebateStrategy

    for name, cls in [
        ("amm", AMMStrategy),
        ("bands", BandsStrategy),
        ("classic_mm", ClassicMMStrategy),
        ("maker_rebate", MakerRebateStrategy),
    ]:
        if name not in _registry:
            _registry[name] = cls
        if PluginRegistry().get_strategy(name) is None:
            PluginRegistry().register_strategy(name, cls)
```

**Note:** The `@register("maker_rebate")` decorator on `MakerRebateStrategy`
already handles registration when the module is imported. Adding the explicit
entry in `register_builtin_strategies()` provides a second registration path
for the case where the decorator hasn't fired (e.g., eager imports). Either
single-source may be sufficient — both are kept for consistency with existing
strategies.

---

### Task 7: Unit tests

**File:** `tests/strategies/market_making/maker_rebate/test_pair_snapshot.py`

| # | Test name | What it covers |
|---|---|---|
| 1 | `test_pair_snapshot_construction` | Build from individual YES/NO prices, verify derived fields |
| 2 | `test_rebate_spread_computed` | YES=0.60, NO=0.35 → combined=0.95, spread=0.05 |
| 3 | `test_implicit_risk_free_computed` | YES_ask=0.61, NO_ask=0.36 → risk_free=0.03 |
| 4 | `test_zero_mid_price` | Both mids=0 → combined=0, spread=1.0 |
| 5 | `test_no_bid_side` | YES_bid=0, NO_bid=0.35 → combined_mid still computed |

**File:** `tests/strategies/market_making/maker_rebate/test_pricing.py`

| # | Test name | What it covers |
|---|---|---|
| 1 | `test_detect_viable_opportunity` | YES=0.60, NO=0.35 → returns (yes_price, no_price, spread) |
| 2 | `test_spread_below_minimum` | YES=0.60, NO=0.395 → captured spread < min → None |
| 3 | `test_no_bid_on_one_side` | YES_bid=0 → returns None |
| 4 | `test_no_bid_on_both_sides` | Both bids=0 → returns None |
| 5 | `test_fee_buffer_erodes_spread` | High fee buffer makes profitable spread unviable |
| 6 | `test_price_buffer_applied` | Verify yes_price = yes_bid * (1 - buffer) |
| 7 | `test_exact_min_spread` | captured == min_rebate_spread → returns prices |

**File:** `tests/strategies/market_making/maker_rebate/test_sizing.py`

| # | Test name | What it covers |
|---|---|---|
| 1 | `test_equal_sizes` | Returns (size, size) with equal values |
| 2 | `test_clamp_to_max_exposure` | Combined price * size > max_exposure → clamped |
| 3 | `test_below_min_order_size` | max_cost too small → returns None |
| 4 | `test_clamp_to_max_order_size` | Size hits max_order_size cap |
| 5 | `test_global_debt_ceiling` | total_exposure + new cost > max_total → None |
| 6 | `test_global_debt_clamped` | Partial global headroom → reduced size |
| 7 | `test_global_ceiling_disabled` | use_debt_ceiling=False → no global cap |
| 8 | `test_zero_combined_price` | Combined price = 0 → returns None |

**File:** `tests/strategies/market_making/maker_rebate/test_strategy.py`

| # | Test name | What it covers |
|---|---|---|
| 1 | `test_analyze_returns_intent` | Viable pair → StrategyIntent with 2 orders, 2 cancels |
| 2 | `test_analyze_duplicate_condition` | Same condition called twice → None on second call |
| 3 | `test_analyze_no_opportunity` | Spread too small → None |
| 4 | `test_analyze_after_filled` | mark_filled removes tracking → produces new intent |
| 5 | `test_analyze_wrong_type` | Passing MarketSnapshot instead of PairSnapshot → TypeError |
| 6 | `test_mark_partial_fill` | One side filled → state updated, still blocked |
| 7 | `test_active_conditions_list` | Returns condition IDs being worked |
| 8 | `test_reset_clears_state` | reset() removes all active conditions |
| 9 | `test_order_metadata_contains_condition` | OrderIntent.metadata includes condition_id |
| 10 | `test_cancel_for_both_markets` | Two CancelIntent entries (one per market) |
| 11 | `test_orders_are_buy_side` | Both OrderIntents have OrderSide.BUY |

---

### Task 8: Run full test suite

Commands:

```bash
python -m pytest tests/strategies/market_making/maker_rebate/ -v
python -m pytest tests/ -x --timeout=30 -q
```

Expected outcomes:
- All ~25 unit tests pass.
- Zero regressions in the full suite (existing 211+ tests).

---

### Task 9: Integration considerations (documented, not code)

The following integration points are **not** implemented as code in Phase 23
but must be accounted for in the orchestrator layer that calls the strategy:

1. **PairSnapshot construction**: The orchestrator must fetch `MarketSnapshot`
   for both YES and NO markets of a condition and call
   `PairSnapshot.__init__()` with both. The mapping from
   `(market_id, outcome)` to `condition_id` lives in
   `PairLifecycleManager._market_to_condition`.

2. **USDC balance pre-check**: Before calling `analyze()`, the orchestrator
   should verify `wallet USDC balance >= order_costs` to avoid split failures.

3. **Fill event routing**: The orchestrator must call `mark_filled()` on the
   strategy when both YES and NO fills are confirmed (via WebSocket fill
   events). Partial fills are routed via `mark_partial_fill()`.

4. **Workflow state machine lifecycle**: After `mark_filled()`, the
   orchestrator issues `WorkflowCommand(START, "rebate-<id>")` to the
   `WorkflowRunner`, which creates a `RebateStateMachine` instance. Pair
   lifecycle commands (SPLIT → MERGE → REDEEM) are issued as the workflow
   progresses.

5. **Tick frequency**: The strategy produces intents at most once per
   condition. After placement, `analyze()` returns `None` until
   `mark_filled()` is called, preventing unnecessary cancel-and-replace
   churn.
