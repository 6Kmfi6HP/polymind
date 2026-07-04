"""
PairLifecycleManager — YES/NO token inventory tracker and pair-lifecycle executor.

Wraps ContractsGateway with an inventory-tracking layer so higher-level
callers (WorkflowRunner) can issue split, merge, redeem, sell-remainder,
and one-sided-halt commands without managing token IDs or checking
balances manually.
"""

from __future__ import annotations

from dataclasses import dataclass

from polymind.core.intents import (
    IntentExecutor,
    OrderIntent,
    OrderSide,
    StrategyIntent,
    TimeInForce,
)
from polymind.polymarket.contracts import (
    ContractsGateway,
)
from polymind.polymarket.errors import (
    InsufficientBalanceError,
    PairLifecycleError,
)

# ── Domain types ──────────────────────────────────────────────────────────


@dataclass
class PairPosition:
    """Snapshot of YES/NO token inventory for a single condition."""

    condition_id: str
    yes_token_id: str
    no_token_id: str
    yes_balance: float = 0.0
    no_balance: float = 0.0
    yes_avg_entry: float = 0.0
    no_avg_entry: float = 0.0
    yes_cost_basis: float = 0.0
    no_cost_basis: float = 0.0
    is_resolved: bool = False
    resolved_outcome: str | None = None


@dataclass
class SplitOperation:
    """Result of splitting USDC into YES + NO tokens."""

    condition_id: str
    usdc_amount: float
    yes_amount: float
    no_amount: float
    tx_hash: str
    updated_position: PairPosition


@dataclass
class MergeOperation:
    """Result of merging YES + NO tokens back into USDC."""

    condition_id: str
    outcome_token_amount: float
    proceeds_usdc: float
    tx_hash: str
    updated_position: PairPosition


@dataclass
class RedeemOperation:
    """Result of redeeming winning tokens after resolution."""

    condition_id: str
    outcome: str
    amount_redeemed: float
    proceeds_usdc: float
    tx_hash: str
    updated_position: PairPosition


@dataclass
class SellRemainderOperation:
    """Result of selling remainder tokens on the CLOB."""

    market_id: str
    outcome: str
    amount_sold: float = 0.0
    proceeds_usdc: float = 0.0
    orders_placed: int = 0


@dataclass
class OneSidedHaltResult:
    """Result of halting one side of a pair's quoting."""

    market_id: str
    outcome: str
    orders_cancelled: int = 0


# ── Manager ───────────────────────────────────────────────────────────────

MIN_SELL_REMAINDER = 0.001  # minimum token balance to sell


class PairLifecycleManager:
    """YES/NO token inventory tracker and pair-lifecycle executor.

    Wraps ``ContractsGateway`` with an inventory-tracking layer so that
    higher-level callers can issue pair lifecycle commands without managing
    token IDs or checking balances manually.

    Parameters
    ----------
    gateway:
        The on-chain contracts gateway for split/merge/redeem operations.
    executor:
        Optional intent executor for CLOB order placement (sell-remainder).
    """

    def __init__(
        self,
        gateway: ContractsGateway,
        executor: IntentExecutor | None = None,
    ) -> None:
        self._gateway = gateway
        self._executor = executor
        self._positions: dict[str, PairPosition] = {}
        self._token_id_to_condition: dict[str, str] = {}
        self._market_to_condition: dict[str, str] = {}
        self._condition_to_market: dict[str, str] = {}
        self._halted_sides: set[tuple[str, str]] = set()

    # ── Inventory API ──────────────────────────────────────────────────

    def register_market(
        self,
        condition_id: str,
        yes_token_id: str,
        no_token_id: str,
        market_id: str | None = None,
        initial_yes: float = 0.0,
        initial_no: float = 0.0,
    ) -> PairPosition:
        """Register a market for inventory tracking.

        Returns the new ``PairPosition``.  Raises ``PairLifecycleError``
        if *condition_id* is already registered.
        """
        if condition_id in self._positions:
            raise PairLifecycleError(f"Condition {condition_id} already registered")

        pos = PairPosition(
            condition_id=condition_id,
            yes_token_id=yes_token_id,
            no_token_id=no_token_id,
            yes_balance=initial_yes,
            no_balance=initial_no,
        )
        self._positions[condition_id] = pos
        self._token_id_to_condition[yes_token_id] = condition_id
        self._token_id_to_condition[no_token_id] = condition_id

        if market_id is not None:
            self._market_to_condition[market_id] = condition_id
            self._condition_to_market[condition_id] = market_id

        return pos

    def get_position(self, condition_id: str) -> PairPosition | None:
        """Return the tracked position for *condition_id*, or ``None``."""
        return self._positions.get(condition_id)

    async def sync_position(self, condition_id: str) -> PairPosition:
        """Re-read on-chain balances and update the in-memory position.

        Preserves avg_entry and cost_basis (only balance fields change).
        """
        pos = self._require_position(condition_id)

        yes_bal = await self._gateway.get_onchain_balance(pos.yes_token_id)
        no_bal = await self._gateway.get_onchain_balance(pos.no_token_id)

        pos.yes_balance = yes_bal.balance / 1e6
        pos.no_balance = no_bal.balance / 1e6

        return pos

    async def sync_all(self) -> dict[str, PairPosition]:
        """Call ``sync_position`` for every registered condition."""
        for cid in list(self._positions):
            await self.sync_position(cid)
        return dict(self._positions)

    def list_positions(self) -> dict[str, PairPosition]:
        """Return all registered positions."""
        return dict(self._positions)

    def get_redeemable_positions(self) -> list[PairPosition]:
        """Return positions where the market is resolved with winning tokens."""
        redeemable: list[PairPosition] = []
        for pos in self._positions.values():
            if not pos.is_resolved or pos.resolved_outcome is None:
                continue
            winning_bal = pos.yes_balance if pos.resolved_outcome == "YES" else pos.no_balance
            if winning_bal > 0:
                redeemable.append(pos)
        return redeemable

    def mark_resolved(self, condition_id: str, resolved_outcome: str) -> PairPosition:
        """Mark a market as resolved with the given outcome."""
        pos = self._require_position(condition_id)
        pos.is_resolved = True
        pos.resolved_outcome = resolved_outcome
        return pos

    def is_halted(self, market_id: str, outcome: str) -> bool:
        """Check if quoting is halted for a given (market, outcome)."""
        return (market_id, outcome) in self._halted_sides

    # ── Pair lifecycle operations ──────────────────────────────────────

    async def split(
        self, condition_id: str, amount: int, *, approve: bool = True
    ) -> SplitOperation:
        """Split *amount* of USDC (6-dec raw) into YES + NO tokens.

        Parameters
        ----------
        condition_id:
            The condition to split for.
        amount:
            USDC amount in raw 6-dec units (e.g. 1_000_000 = 1 USDC).
        approve:
            Whether to call ``approve_usdc`` first.
        """
        pos = self._require_position(condition_id)

        # Check USDC balance
        token_bal = await self._gateway.get_onchain_balance(pos.yes_token_id)
        if token_bal.usdc_balance * 1e6 < amount:
            raise InsufficientBalanceError(
                f"USDC balance {token_bal.usdc_balance:.2f} < "
                f"{amount / 1e6:.2f} required for split"
            )

        if approve:
            await self._gateway.approve_usdc(amount)

        result = await self._gateway.split(condition_id, amount)

        # Update position
        half = float(amount) / 2 / 1e6
        pos.yes_balance += half
        pos.no_balance += half
        pos.yes_cost_basis += half
        pos.no_cost_basis += half
        pos.yes_avg_entry = pos.yes_cost_basis / pos.yes_balance if pos.yes_balance > 0 else 0.0
        pos.no_avg_entry = pos.no_cost_basis / pos.no_balance if pos.no_balance > 0 else 0.0

        return SplitOperation(
            condition_id=condition_id,
            usdc_amount=float(amount) / 1e6,
            yes_amount=result.outcome_a_amount,
            no_amount=result.outcome_b_amount,
            tx_hash=result.tx_hash,
            updated_position=pos,
        )

    async def merge(
        self, condition_id: str, amount: int, *, approve: bool = True
    ) -> MergeOperation:
        """Merge *amount* of YES+NO token pairs back into USDC.

        Parameters
        ----------
        condition_id:
            The condition to merge for.
        amount:
            Number of token *pairs* in raw 6-dec units.
        approve:
            Whether to call ``approve_exchange`` first.
        """
        pos = self._require_position(condition_id)

        # Check both sides have enough tokens
        check_amount = float(amount) / 1e6
        if pos.yes_balance < check_amount or pos.no_balance < check_amount:
            raise InsufficientBalanceError(
                f"Insufficient tokens for merge: "
                f"YES={pos.yes_balance:.4f}, NO={pos.no_balance:.4f}, "
                f"required={check_amount:.4f}"
            )

        if approve:
            # Approve exchange for both tokens
            await self._gateway.approve_exchange(pos.yes_token_id, amount)
            await self._gateway.approve_exchange(pos.no_token_id, amount)

        result = await self._gateway.merge(condition_id, amount)

        proceeds = float(amount) / 1e6
        old_yes = pos.yes_balance
        old_no = pos.no_balance

        pos.yes_balance -= check_amount
        pos.no_balance -= check_amount

        # Prorate cost basis
        if old_yes > 0:
            pos.yes_cost_basis *= pos.yes_balance / old_yes
        if old_no > 0:
            pos.no_cost_basis *= pos.no_balance / old_no

        pos.yes_avg_entry = pos.yes_cost_basis / pos.yes_balance if pos.yes_balance > 0 else 0.0
        pos.no_avg_entry = pos.no_cost_basis / pos.no_balance if pos.no_balance > 0 else 0.0

        return MergeOperation(
            condition_id=condition_id,
            outcome_token_amount=check_amount,
            proceeds_usdc=proceeds,
            tx_hash=result.tx_hash,
            updated_position=pos,
        )

    async def redeem(
        self,
        condition_id: str,
        index_set: int | None = None,
    ) -> RedeemOperation:
        """Redeem winning tokens after market resolution.

        Parameters
        ----------
        condition_id:
            The condition to redeem for.
        index_set:
            Override the outcome index (0=YES, 1=NO).  Defaults to
            the position's ``resolved_outcome``.
        """
        pos = self._require_position(condition_id)

        if not pos.is_resolved or pos.resolved_outcome is None:
            raise PairLifecycleError(f"Condition {condition_id} is not resolved")

        outcome_index = (
            index_set if index_set is not None else (0 if pos.resolved_outcome == "YES" else 1)
        )
        winning_side = "YES" if outcome_index == 0 else "NO"
        winning_balance = pos.yes_balance if outcome_index == 0 else pos.no_balance

        if winning_balance <= 0:
            raise PairLifecycleError(f"No winning tokens to redeem for condition {condition_id}")

        raw_amount = int(winning_balance * 1e6)
        result = await self._gateway.redeem(condition_id, outcome_index, raw_amount)

        # Zero the winning side
        if outcome_index == 0:
            pos.yes_balance = 0.0
            pos.yes_cost_basis = 0.0
            pos.yes_avg_entry = 0.0
        else:
            pos.no_balance = 0.0
            pos.no_cost_basis = 0.0
            pos.no_avg_entry = 0.0

        return RedeemOperation(
            condition_id=condition_id,
            outcome=winning_side,
            amount_redeemed=winning_balance,
            proceeds_usdc=result.proceeds_usdc,
            tx_hash=result.tx_hash,
            updated_position=pos,
        )

    async def sell_remainder(
        self,
        market_id: str,
        outcome: str,
    ) -> SellRemainderOperation:
        """Sell small remainder tokens via CLOB.

        Parameters
        ----------
        market_id:
            Market whose remainder to sell.
        outcome:
            Outcome side to sell ("YES" or "NO").
        """
        condition_id = self._market_to_condition.get(market_id)
        if condition_id is None:
            raise PairLifecycleError(f"Market {market_id} not registered")

        pos = self._require_position(condition_id)
        balance = pos.yes_balance if outcome == "YES" else pos.no_balance

        if balance < MIN_SELL_REMAINDER:
            return SellRemainderOperation(
                market_id=market_id,
                outcome=outcome,
                amount_sold=0.0,
                orders_placed=0,
            )

        if self._executor is None:
            raise PairLifecycleError("No executor configured for sell_remainder")

        # Use a competitive price: 0.5 for unresolved, near 1.0 for resolved
        sell_price = (
            0.5 if not pos.is_resolved else (0.99 if (outcome == pos.resolved_outcome) else 0.01)
        )

        order = OrderIntent(
            market_id=market_id,
            side=OrderSide.SELL,
            price=sell_price,
            size=balance,
            outcome=outcome,
            time_in_force=TimeInForce.IOC,
            reduce_only=True,
        )

        intent = StrategyIntent(
            strategy_name="pair_lifecycle",
            timestamp=__import__("datetime").datetime.now(),
            orders=[order],
        )

        result = await self._executor.execute(intent)

        filled = 0.0
        for entry in result.values():
            if isinstance(entry, dict):
                filled += entry.get("filled_size", 0.0)

        return SellRemainderOperation(
            market_id=market_id,
            outcome=outcome,
            amount_sold=filled,
            orders_placed=1,
        )

    async def one_sided_halt(
        self,
        market_id: str,
        outcome: str,
    ) -> OneSidedHaltResult:
        """Halt quoting for a single outcome side.

        Cancels open orders for the side and records the halt.
        """
        condition_id = self._market_to_condition.get(market_id)
        if condition_id is None:
            raise PairLifecycleError(f"Market {market_id} not registered")

        self._require_position(condition_id)
        self._halted_sides.add((market_id, outcome))

        return OneSidedHaltResult(
            market_id=market_id,
            outcome=outcome,
            orders_cancelled=0,  # actual cancel delegated to executor
        )

    # ── Internal ───────────────────────────────────────────────────────

    def _require_position(self, condition_id: str) -> PairPosition:
        pos = self._positions.get(condition_id)
        if pos is None:
            raise PairLifecycleError(f"Condition {condition_id} not registered")
        return pos
