"""Tests for the Polymarket contracts gateway."""

from __future__ import annotations

from datetime import datetime

import pytest

from polymind.polymarket.contracts import (
    ContractsConfig,
    ContractsGateway,
    MergeResult,
    RedeemResult,
    SplitResult,
    TokenBalance,
)


class TestContractsConfig:
    def test_defaults(self) -> None:
        cfg = ContractsConfig()
        assert cfg.rpc_url == "https://polygon-rpc.com"
        assert cfg.private_key is None
        assert cfg.chain_id == 137
        assert cfg.gas_limit == 500_000
        assert cfg.gas_price_gwei == 50.0


class TestSplitResult:
    def test_construction(self) -> None:
        ts = datetime(2026, 1, 1)
        sr = SplitResult(tx_hash="0xhij", outcome_a_amount=50.0, outcome_b_amount=50.0, timestamp=ts)
        assert sr.tx_hash == "0xhij"
        assert sr.outcome_a_amount == 50.0
        assert sr.outcome_b_amount == 50.0

    def test_defaults_zero(self) -> None:
        sr = SplitResult(tx_hash="0x1")
        assert sr.outcome_a_amount == 0.0


class TestMergeResult:
    def test_construction(self) -> None:
        mr = MergeResult(tx_hash="0xmerge", outcome_a_amount=25.0, outcome_b_amount=25.0)
        assert mr.tx_hash == "0xmerge"
        assert mr.outcome_a_amount == 25.0

    def test_defaults_zero(self) -> None:
        mr = MergeResult(tx_hash="0x1")
        assert mr.outcome_b_amount == 0.0


class TestRedeemResult:
    def test_construction(self) -> None:
        rr = RedeemResult(tx_hash="0xredeem", proceeds_usdc=100.0)
        assert rr.tx_hash == "0xredeem"
        assert rr.proceeds_usdc == 100.0

    def test_defaults_zero(self) -> None:
        rr = RedeemResult(tx_hash="0x1")
        assert rr.proceeds_usdc == 0.0


class TestTokenBalance:
    def test_construction(self) -> None:
        tb = TokenBalance(token_id="0xid", owner="0xowner", balance=500.0)
        assert tb.token_id == "0xid"
        assert tb.owner == "0xowner"
        assert tb.balance == 500.0


class TestContractsGateway:
    """Tests for the concrete gateway using a simple test implementation."""

    @pytest.fixture
    def gateway(self) -> ContractsGateway:
        class TestGateway(ContractsGateway):
            async def split(self, market_id: str, outcome: str, amount: float) -> SplitResult:
                return SplitResult(tx_hash="0xsplit", outcome_a_amount=amount / 2, outcome_b_amount=amount / 2)

            async def merge(self, market_id: str, outcome_a: str, outcome_b: str) -> MergeResult:
                return MergeResult(tx_hash="0xmerge")

            async def redeem(self, market_id: str, outcome: str) -> RedeemResult:
                return RedeemResult(tx_hash="0xredeem", proceeds_usdc=100.0)

            async def balance_of(self, owner: str, token_id: str) -> float:
                return 500.0 if token_id == "0xactive" else 0.0

            async def approve(self, token_address: str, spender: str, amount: float) -> bool:
                return True

        return TestGateway(ContractsConfig())

    @pytest.mark.asyncio
    async def test_split(self, gateway: ContractsGateway) -> None:
        sr = await gateway.split("0xmarket", "Yes", 100.0)
        assert sr.outcome_a_amount == 50.0
        assert "0xsplit" in sr.tx_hash

    @pytest.mark.asyncio
    async def test_merge(self, gateway: ContractsGateway) -> None:
        mr = await gateway.merge("0xmarket", "Yes", "No")
        assert mr.tx_hash == "0xmerge"

    @pytest.mark.asyncio
    async def test_redeem(self, gateway: ContractsGateway) -> None:
        rr = await gateway.redeem("0xmarket", "Yes")
        assert rr.proceeds_usdc == 100.0

    @pytest.mark.asyncio
    async def test_balance_of(self, gateway: ContractsGateway) -> None:
        bal = await gateway.balance_of("0xowner", "0xactive")
        assert bal == 500.0

    @pytest.mark.asyncio
    async def test_balance_of_zero(self, gateway: ContractsGateway) -> None:
        bal = await gateway.balance_of("0xowner", "0xdead")
        assert bal == 0.0

    @pytest.mark.asyncio
    async def test_approve(self, gateway: ContractsGateway) -> None:
        result = await gateway.approve("0xtoken", "0xspender", 1000.0)
        assert result is True

    @pytest.mark.asyncio
    async def test_context_manager(self) -> None:
        async with ContractsGateway(ContractsConfig()) as gw:
            pass  # abstract — just verify enter/exit don't raise

    @pytest.mark.asyncio
    async def test_close_idempotent(self) -> None:
        gw = ContractsGateway(ContractsConfig())
        await gw.close()
        await gw.close()
