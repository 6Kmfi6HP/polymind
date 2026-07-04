"""
Tests for PairLifecycleManager — inventory tracking and pair operations.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from polymind.core.intents import IntentExecutor
from polymind.polymarket.contracts import (
    ContractsGateway,
    MergeResult,
    OnChainBalance,
    RedeemResult,
    SplitResult,
    TransactionResult,
)
from polymind.polymarket.errors import (
    InsufficientBalanceError,
    PairLifecycleError,
)
from polymind.polymarket.pair_lifecycle import (
    PairLifecycleManager,
)


@pytest.fixture
def mock_gateway() -> MagicMock:
    gw = MagicMock(spec=ContractsGateway)
    gw.get_onchain_balance = AsyncMock()
    gw.split = AsyncMock()
    gw.merge = AsyncMock()
    gw.redeem = AsyncMock()
    gw.approve_usdc = AsyncMock()
    gw.approve_exchange = AsyncMock()
    return gw


@pytest.fixture
def mock_executor() -> AsyncMock:
    ex = AsyncMock(spec=IntentExecutor)
    ex.execute = AsyncMock(return_value={})
    return ex


@pytest.fixture
def manager(mock_gateway: MagicMock) -> PairLifecycleManager:
    return PairLifecycleManager(gateway=mock_gateway)


@pytest.fixture
def manager_with_executor(
    mock_gateway: MagicMock,
    mock_executor: AsyncMock,
) -> PairLifecycleManager:
    return PairLifecycleManager(gateway=mock_gateway, executor=mock_executor)


C1 = "0xabcd"
YES_ID = "123"
NO_ID = "456"


class TestPairLifecycleManagerInventory:
    """Tests for register, get, list, sync, mark_resolved."""

    def test_register_market(self, manager: PairLifecycleManager):
        pos = manager.register_market(C1, YES_ID, NO_ID, market_id="mkt1")
        assert pos.condition_id == C1
        assert pos.yes_token_id == YES_ID
        assert pos.no_token_id == NO_ID
        assert pos.yes_balance == 0.0
        assert pos.no_balance == 0.0
        assert pos.is_resolved is False

    def test_register_duplicate(self, manager: PairLifecycleManager):
        manager.register_market(C1, YES_ID, NO_ID)
        with pytest.raises(PairLifecycleError, match="already registered"):
            manager.register_market(C1, "789", "012")

    def test_get_position_nonexistent(self, manager: PairLifecycleManager):
        assert manager.get_position("nonexistent") is None

    def test_get_position_existing(self, manager: PairLifecycleManager):
        manager.register_market(C1, YES_ID, NO_ID)
        pos = manager.get_position(C1)
        assert pos is not None
        assert pos.condition_id == C1

    async def test_sync_position(self, manager: PairLifecycleManager, mock_gateway: MagicMock):
        manager.register_market(C1, YES_ID, NO_ID)

        mock_gateway.get_onchain_balance.side_effect = [
            OnChainBalance(token_id=YES_ID, balance=2_000_000, usdc_balance=100.0),
            OnChainBalance(token_id=NO_ID, balance=3_000_000, usdc_balance=50.0),
        ]

        pos = await manager.sync_position(C1)
        assert pos.yes_balance == 2.0  # 2_000_000 / 1e6
        assert pos.no_balance == 3.0  # 3_000_000 / 1e6

    async def test_sync_all(self, manager: PairLifecycleManager, mock_gateway: MagicMock):
        manager.register_market(C1, YES_ID, NO_ID)
        manager.register_market("0xother", "789", "012")

        mock_gateway.get_onchain_balance.return_value = OnChainBalance(
            token_id="", balance=1_000_000, usdc_balance=10.0
        )

        positions = await manager.sync_all()
        assert len(positions) == 2

    def test_list_positions(self, manager: PairLifecycleManager):
        manager.register_market(C1, YES_ID, NO_ID)
        manager.register_market("0xother", "789", "012")
        positions = manager.list_positions()
        assert len(positions) == 2

    def test_mark_resolved(self, manager: PairLifecycleManager):
        manager.register_market(C1, YES_ID, NO_ID)
        pos = manager.mark_resolved(C1, "YES")
        assert pos.is_resolved is True
        assert pos.resolved_outcome == "YES"

    def test_get_redeemable_positions(self, manager: PairLifecycleManager):
        manager.register_market(C1, YES_ID, NO_ID, initial_yes=10.0, initial_no=5.0)
        manager.register_market("0xother", "789", "012", initial_yes=0.0, initial_no=0.0)

        manager.mark_resolved(C1, "YES")
        # other is unresolved

        redeemable = manager.get_redeemable_positions()
        assert len(redeemable) == 1
        assert redeemable[0].condition_id == C1

    def test_get_redeemable_no_winning_balance(self, manager: PairLifecycleManager):
        manager.register_market(C1, YES_ID, NO_ID, initial_yes=0.0, initial_no=0.0)
        manager.mark_resolved(C1, "YES")
        redeemable = manager.get_redeemable_positions()
        assert len(redeemable) == 0

    def test_is_halted(self, manager: PairLifecycleManager):
        assert manager.is_halted("mkt1", "YES") is False


class TestPairLifecycleManagerSplit:
    """Tests for the split operation."""

    async def test_split_success(self, manager: PairLifecycleManager, mock_gateway: MagicMock):
        manager.register_market(C1, YES_ID, NO_ID)

        mock_gateway.get_onchain_balance.return_value = OnChainBalance(
            token_id=YES_ID,
            balance=0,
            usdc_balance=200.0,
        )
        mock_gateway.split.return_value = SplitResult(
            tx_hash="0xsplit",
            outcome_a_amount=50.0,
            outcome_b_amount=50.0,
        )
        mock_gateway.approve_usdc.return_value = TransactionResult(
            tx_hash="0xapprove",
            status="CONFIRMED",
            block_number=1,
            gas_used=50000,
            gas_price_gwei=50.0,
        )

        result = await manager.split(C1, 100_000_000)  # 100 USDC

        assert result.usdc_amount == 100.0
        assert result.tx_hash == "0xsplit"
        assert result.updated_position.yes_balance == 50.0
        assert result.updated_position.no_balance == 50.0
        assert result.updated_position.yes_cost_basis == 50.0
        assert result.updated_position.no_cost_basis == 50.0

    async def test_split_insufficient_usdc(
        self, manager: PairLifecycleManager, mock_gateway: MagicMock
    ):
        manager.register_market(C1, YES_ID, NO_ID)

        mock_gateway.get_onchain_balance.return_value = OnChainBalance(
            token_id=YES_ID,
            balance=0,
            usdc_balance=5.0,
        )

        with pytest.raises(InsufficientBalanceError, match="USDC balance"):
            await manager.split(C1, 100_000_000)

    async def test_split_unregistered(self, manager: PairLifecycleManager):
        with pytest.raises(PairLifecycleError, match="not registered"):
            await manager.split("unknown", 1000)


class TestPairLifecycleManagerMerge:
    """Tests for the merge operation."""

    async def test_merge_success(self, manager: PairLifecycleManager, mock_gateway: MagicMock):
        manager.register_market(C1, YES_ID, NO_ID, initial_yes=100.0, initial_no=100.0)

        mock_gateway.merge.return_value = MergeResult(
            tx_hash="0xmerge",
            outcome_a_amount=50.0,
            outcome_b_amount=50.0,
        )
        mock_gateway.approve_exchange.return_value = TransactionResult(
            tx_hash="0xapp",
            status="CONFIRMED",
            block_number=1,
            gas_used=50000,
            gas_price_gwei=50.0,
        )

        result = await manager.merge(C1, 50_000_000)  # 50 pairs

        assert result.outcome_token_amount == 50.0
        assert result.proceeds_usdc == 50.0
        assert result.updated_position.yes_balance == 50.0
        assert result.updated_position.no_balance == 50.0

    async def test_merge_insufficient_balance(self, manager: PairLifecycleManager):
        manager.register_market(C1, YES_ID, NO_ID, initial_yes=1.0, initial_no=100.0)

        with pytest.raises(InsufficientBalanceError, match="Insufficient tokens"):
            await manager.merge(C1, 50_000_000)

    async def test_merge_unregistered(self, manager: PairLifecycleManager):
        with pytest.raises(PairLifecycleError, match="not registered"):
            await manager.merge("unknown", 1000)


class TestPairLifecycleManagerRedeem:
    """Tests for the redeem operation."""

    async def test_redeem_success(self, manager: PairLifecycleManager, mock_gateway: MagicMock):
        manager.register_market(C1, YES_ID, NO_ID, initial_yes=25.0, initial_no=75.0)
        manager.mark_resolved(C1, "YES")

        mock_gateway.redeem.return_value = RedeemResult(
            tx_hash="0xredeem",
            proceeds_usdc=25.0,
        )

        result = await manager.redeem(C1)

        assert result.outcome == "YES"
        assert result.amount_redeemed == 25.0
        assert result.proceeds_usdc == 25.0
        # Winning side zeroed
        assert result.updated_position.yes_balance == 0.0
        assert result.updated_position.yes_cost_basis == 0.0
        # NO side preserved
        assert result.updated_position.no_balance == 75.0

    async def test_redeem_unresolved(self, manager: PairLifecycleManager):
        manager.register_market(C1, YES_ID, NO_ID, initial_yes=10.0, initial_no=10.0)

        with pytest.raises(PairLifecycleError, match="not resolved"):
            await manager.redeem(C1)

    async def test_redeem_zero_balance(self, manager: PairLifecycleManager):
        manager.register_market(C1, YES_ID, NO_ID, initial_yes=0.0, initial_no=10.0)
        manager.mark_resolved(C1, "YES")

        with pytest.raises(PairLifecycleError, match="No winning tokens"):
            await manager.redeem(C1)

    async def test_redeem_none_unregistered(self, manager: PairLifecycleManager):
        with pytest.raises(PairLifecycleError, match="not registered"):
            await manager.redeem("unknown")


class TestPairLifecycleManagerSellRemainder:
    """Tests for sell_remainder operation."""

    async def test_sell_remainder_small_balance(self, manager: PairLifecycleManager):
        manager.register_market(
            C1, YES_ID, NO_ID, market_id="mkt1", initial_yes=0.0001, initial_no=0.0
        )
        result = await manager.sell_remainder("mkt1", "YES")
        assert result.orders_placed == 0

    async def test_sell_remainder_no_executor(self, manager: PairLifecycleManager):
        manager.register_market(
            C1, YES_ID, NO_ID, market_id="mkt1", initial_yes=1.0, initial_no=0.0
        )
        with pytest.raises(PairLifecycleError, match="No executor"):
            await manager.sell_remainder("mkt1", "YES")

    async def test_sell_remainder_with_executor(
        self,
        manager_with_executor: PairLifecycleManager,
        mock_executor: AsyncMock,
    ):
        manager_with_executor.register_market(
            C1, YES_ID, NO_ID, market_id="mkt1", initial_yes=5.0, initial_no=0.0
        )
        mock_executor.execute.return_value = {
            "order1": {"filled_size": 4.5, "status": "FILLED"},
        }

        result = await manager_with_executor.sell_remainder("mkt1", "YES")
        assert result.orders_placed == 1
        assert result.amount_sold == 4.5

    async def test_sell_remainder_unregistered(self, manager_with_executor: PairLifecycleManager):
        with pytest.raises(PairLifecycleError, match="not registered"):
            await manager_with_executor.sell_remainder("unknown_mkt", "YES")


class TestPairLifecycleManagerOneSidedHalt:
    """Tests for one_sided_halt operation."""

    async def test_one_sided_halt(self, manager: PairLifecycleManager):
        manager.register_market(C1, YES_ID, NO_ID, market_id="mkt1")
        result = await manager.one_sided_halt("mkt1", "YES")
        assert result.market_id == "mkt1"
        assert result.outcome == "YES"
        assert manager.is_halted("mkt1", "YES") is True

    async def test_one_sided_halt_unregistered(self, manager: PairLifecycleManager):
        with pytest.raises(PairLifecycleError, match="not registered"):
            await manager.one_sided_halt("unknown", "YES")
