"""
Integration tests for PairLifecycleManager + ContractsGateway.

Uses mocked Web3 layer to test the full stack end-to-end without a real RPC.
"""

from __future__ import annotations

from datetime import datetime
from unittest.mock import AsyncMock, MagicMock

import pytest

from polymind.polymarket.contracts import (
    ContractsConfig,
    ContractsGateway,
    OnChainBalance,
    SplitResult,
)
from polymind.polymarket.pair_lifecycle import (
    PairLifecycleManager,
)


@pytest.fixture
def gateway() -> ContractsGateway:
    gw = ContractsGateway(ContractsConfig(private_key="0xdeadbeef" * 4, rpc_url="https://test.url"))
    gw._w3 = MagicMock()
    gw._account = MagicMock()
    gw._account.address = "0xTest"
    return gw


@pytest.fixture
def manager(gateway: ContractsGateway) -> PairLifecycleManager:
    return PairLifecycleManager(gateway=gateway)


C1 = "0xabc123"
YES_ID = "111"
NO_ID = "222"


def _make_onchain_balance(token_id: str, balance: int = 0, usdc: float = 0.0) -> OnChainBalance:
    return OnChainBalance(token_id=token_id, balance=balance, usdc_balance=usdc)


class TestPairLifecycleManagerIntegration:
    """Full-stack integration tests with mocked chain calls."""

    @pytest.mark.asyncio
    async def test_register_then_split(
        self,
        manager: PairLifecycleManager,
        gateway: ContractsGateway,
    ):
        """Register a market, split USDC, verify position updated via gateway."""
        manager.register_market(C1, YES_ID, NO_ID, market_id="mkt1")

        # Mock on-chain balance to show sufficient USDC
        async def fake_balance(token_id: str) -> OnChainBalance:
            return _make_onchain_balance(token_id, usdc=500.0)

        gateway.get_onchain_balance = AsyncMock(side_effect=fake_balance)
        gateway.approve_usdc = AsyncMock(
            return_value=MagicMock(tx_hash="0xapp", status="CONFIRMED")
        )

        # Mock split to return a valid result
        gateway.split = AsyncMock(
            return_value=SplitResult(
                tx_hash="0xsplit123",
                outcome_a_amount=25.0,
                outcome_b_amount=25.0,
                timestamp=datetime(2026, 7, 4),
            )
        )

        result = await manager.split(C1, 50_000_000)  # 50 USDC

        assert result.usdc_amount == 50.0
        assert result.yes_amount == 25.0
        assert result.no_amount == 25.0
        assert result.tx_hash == "0xsplit123"

        pos = manager.get_position(C1)
        assert pos is not None
        assert pos.yes_balance == 25.0
        assert pos.no_balance == 25.0

    @pytest.mark.asyncio
    async def test_register_then_merge(
        self,
        manager: PairLifecycleManager,
        gateway: ContractsGateway,
    ):
        """Register, set initial balance, merge pairs back."""
        manager.register_market(
            C1,
            YES_ID,
            NO_ID,
            market_id="mkt1",
            initial_yes=50.0,
            initial_no=50.0,
        )

        gateway.approve_exchange = AsyncMock(
            return_value=MagicMock(tx_hash="0xapp", status="CONFIRMED")
        )
        gateway.merge = AsyncMock(
            return_value=MagicMock(
                tx_hash="0xmerge456",
                outcome_a_amount=25.0,
                outcome_b_amount=25.0,
            )
        )

        result = await manager.merge(C1, 25_000_000)  # 25 pairs

        assert result.outcome_token_amount == 25.0
        assert result.proceeds_usdc == 25.0
        assert result.updated_position.yes_balance == 25.0
        assert result.updated_position.no_balance == 25.0

    @pytest.mark.asyncio
    async def test_register_resolve_redeem(
        self,
        manager: PairLifecycleManager,
        gateway: ContractsGateway,
    ):
        """Full lifecycle: register -> mark_resolved -> redeem."""
        manager.register_market(
            C1,
            YES_ID,
            NO_ID,
            market_id="mkt1",
            initial_yes=30.0,
            initial_no=70.0,
        )
        manager.mark_resolved(C1, "YES")

        gateway.redeem = AsyncMock(
            return_value=MagicMock(
                tx_hash="0xredeem789",
                proceeds_usdc=30.0,
            )
        )

        result = await manager.redeem(C1)

        assert result.outcome == "YES"
        assert result.amount_redeemed == 30.0
        assert result.proceeds_usdc == 30.0

        pos = manager.get_position(C1)
        assert pos is not None
        assert pos.yes_balance == 0.0  # zeroed after redeem
        assert pos.no_balance == 70.0  # untouched

    @pytest.mark.asyncio
    async def test_sync_from_gateway(
        self,
        manager: PairLifecycleManager,
        gateway: ContractsGateway,
    ):
        """sync_position picks up on-chain balance changes."""
        manager.register_market(C1, YES_ID, NO_ID)

        async def fake_balance(token_id: str) -> OnChainBalance:
            if token_id == YES_ID:
                return _make_onchain_balance(YES_ID, balance=5_000_000, usdc=10.0)
            return _make_onchain_balance(NO_ID, balance=3_000_000, usdc=5.0)

        gateway.get_onchain_balance = AsyncMock(side_effect=fake_balance)

        pos = await manager.sync_position(C1)
        assert pos.yes_balance == 5.0
        assert pos.no_balance == 3.0

        # Change on-chain balances and re-sync
        async def fake_balance2(token_id: str) -> OnChainBalance:
            if token_id == YES_ID:
                return _make_onchain_balance(YES_ID, balance=2_000_000, usdc=10.0)
            return _make_onchain_balance(NO_ID, balance=8_000_000, usdc=5.0)

        gateway.get_onchain_balance = AsyncMock(side_effect=fake_balance2)
        pos = await manager.sync_position(C1)
        assert pos.yes_balance == 2.0
        assert pos.no_balance == 8.0
