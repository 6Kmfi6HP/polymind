"""Tests for the Polymarket contracts gateway — mock-based Web3 integration tests."""

from __future__ import annotations

from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from polymind.polymarket.contracts import (
    ContractsConfig,
    ContractsGateway,
    MergeResult,
    OnChainBalance,
    RedeemResult,
    SplitResult,
    TokenBalance,
    TransactionResult,
)
from polymind.polymarket.errors import ContractError, InsufficientGasError

# ── Domain-type construction tests (pure dataclasses, no mocking needed) ──


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
        sr = SplitResult(
            tx_hash="0xhij", outcome_a_amount=50.0, outcome_b_amount=50.0, timestamp=ts
        )
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


class TestOnChainBalance:
    def test_construction(self) -> None:
        ob = OnChainBalance(token_id="0xabc", balance=100, usdc_balance=50.0)
        assert ob.token_id == "0xabc"
        assert ob.balance == 100
        assert ob.usdc_balance == 50.0
        assert ob.decimals == 6


class TestTransactionResult:
    def test_construction(self) -> None:
        tr = TransactionResult(
            tx_hash="0xhij",
            status="CONFIRMED",
            block_number=12345,
            gas_used=21000,
            gas_price_gwei=50.0,
        )
        assert tr.tx_hash == "0xhij"
        assert tr.status == "CONFIRMED"
        assert tr.block_number == 12345
        assert tr.gas_used == 21000
        assert tr.gas_price_gwei == 50.0


# ── Gateway tests (mock-based) ────────────────────────────────────────────


def _make_mock_receipt(status: int = 1, block: int = 100, gas: int = 21000) -> MagicMock:
    """Helper: build a mock transaction receipt."""
    receipt = MagicMock()
    receipt.status = status
    receipt.blockNumber = block
    receipt.gasUsed = gas
    receipt.transactionHash = b"\x01\x02\x03"
    return receipt


def _make_mock_account(address: str = "0xABCDEF1234567890") -> MagicMock:
    """Helper: build a mock eth-account Account."""
    acct = MagicMock()
    acct.address = address
    return acct


def _make_patched_gateway(config: ContractsConfig | None = None) -> ContractsGateway:
    """Build a gateway with _w3 and _account already wired as mocks."""
    if config is None:
        config = ContractsConfig(private_key="0xdeadbeef" * 4, rpc_url="https://test.url")
    gw = ContractsGateway(config)
    gw._w3 = MagicMock()
    gw._account = _make_mock_account()
    return gw


async def _run_in_thread(fn, *args):
    """Replacement for ``asyncio.to_thread`` that calls *fn(*args)* synchronously
    and wraps the result in a coroutine so ``await`` works."""
    return fn(*args)


class TestContractsGatewayConnect:
    """Tests for Gateway.connect() — Web3 initialisation."""

    @pytest.mark.asyncio
    async def test_connect_initialises_web3(self) -> None:
        gateway = ContractsGateway(ContractsConfig(rpc_url="https://test.url"))
        with (
            patch("polymind.polymarket.contracts.Web3") as mock_w3,
        ):
            mock_w3_instance = MagicMock()
            mock_w3.return_value = mock_w3_instance

            await gateway.connect()

            mock_w3.assert_called_once()
            assert gateway._w3 is not None
            assert gateway._account is None  # no private key

    @pytest.mark.asyncio
    async def test_connect_loads_account_with_private_key(self) -> None:
        gateway = ContractsGateway(
            ContractsConfig(rpc_url="https://test.url", private_key="0xdeadbeef" * 4)
        )
        with (
            patch("polymind.polymarket.contracts.Web3") as mock_w3,
            patch("polymind.polymarket.contracts.eth_account.Account.from_key") as mock_from_key,
        ):
            mock_w3_instance = MagicMock()
            mock_w3.return_value = mock_w3_instance
            mock_account = MagicMock()
            mock_account.address = "0xTest"
            mock_from_key.return_value = mock_account

            await gateway.connect()

            mock_from_key.assert_called_once_with("0xdeadbeef" * 4)
            assert gateway._account is mock_account


class TestContractsGatewayBalance:
    """Tests for balance-of operations."""

    @pytest.mark.asyncio
    async def test_get_onchain_balance_no_account_returns_zero(self) -> None:
        """Without an account, get_onchain_balance should return zero balances."""
        gateway = ContractsGateway(ContractsConfig())
        gateway._w3 = MagicMock()

        result = await gateway.get_onchain_balance("0x123")

        assert result.token_id == "0x123"
        assert result.balance == 0
        assert result.usdc_balance == 0.0

    @pytest.mark.asyncio
    async def test_get_onchain_balance_returns_balances(self) -> None:
        """With an account, get_onchain_balance should query both contracts."""
        gateway = _make_patched_gateway()

        # Mock the contract objects
        mock_token_contract = MagicMock()
        mock_balance_func = MagicMock()
        mock_balance_func.call = MagicMock(return_value=42)
        mock_token_contract.functions.balanceOf.return_value = mock_balance_func

        mock_usdc_contract = MagicMock()
        mock_usdc_balance_func = MagicMock()
        mock_usdc_balance_func.call = MagicMock(return_value=10_000_000)  # 10 USDC
        mock_usdc_contract.functions.balanceOf.return_value = mock_usdc_balance_func

        gateway._w3.eth.contract.side_effect = [mock_token_contract, mock_usdc_contract]

        with patch(
            "asyncio.to_thread",
            new=_run_in_thread,
        ):
            result = await gateway.get_onchain_balance("0xff")

        assert result.token_id == "0xff"
        assert result.balance == 42
        assert result.usdc_balance == 10.0  # 10_000_000 / 1e6

    @pytest.mark.asyncio
    async def test_get_onchain_balance_wraps_exceptions(self) -> None:
        """Web3 exceptions should be wrapped in ContractError."""
        gateway = _make_patched_gateway()
        gateway._w3.eth.contract.side_effect = Exception("RPC failed")

        with pytest.raises(ContractError, match="Failed to fetch on-chain balance"):
            await gateway.get_onchain_balance("0xff")

    @pytest.mark.asyncio
    async def test_backward_compat_balance_of(self) -> None:
        """balance_of() should delegate to get_onchain_balance and return float."""
        gateway = _make_patched_gateway()

        mock_contract = MagicMock()
        mock_balance_func = MagicMock()
        mock_balance_func.call = MagicMock(return_value=99)
        mock_contract.functions.balanceOf.return_value = mock_balance_func

        gateway._w3.eth.contract.return_value = mock_contract

        with patch("asyncio.to_thread", new=_run_in_thread):
            result = await gateway.balance_of("0xowner", "0xabc")

        assert result == 99.0


class TestContractsGatewayApprove:
    """Tests for approve / approve_usdc / approve_exchange."""

    @pytest.mark.asyncio
    async def test_approve_usdc_no_account_raises(self) -> None:
        """Operations that need a private key should raise RuntimeError."""
        gateway = ContractsGateway(ContractsConfig())
        gateway._w3 = MagicMock()

        with pytest.raises(RuntimeError, match="private key"):
            await gateway.approve_usdc(1000)

    @pytest.mark.asyncio
    async def test_approve_usdc_builds_and_sends(self) -> None:
        """approve_usdc should build a tx, sign, send, and wait for receipt."""
        gateway = _make_patched_gateway()

        mock_contract = MagicMock()
        mock_approve_func = MagicMock()
        mock_approve_func.build_transaction = MagicMock(return_value={"to": "0xCTF", "data": "0x"})
        mock_contract.functions.approve.return_value = mock_approve_func
        gateway._w3.eth.contract.return_value = mock_contract

        # Wire _build_tx_params dependencies
        gateway._w3.to_wei.return_value = 50_000_000_000
        gateway._w3.eth.get_transaction_count.return_value = 5

        # Wire _send_transaction dependencies
        gateway._account.sign_transaction.return_value = MagicMock(raw_transaction=b"0xsigned")
        gateway._w3.eth.send_raw_transaction.return_value = b"\xab\xcd"
        gateway._w3.eth.wait_for_transaction_receipt.return_value = _make_mock_receipt()

        with patch("asyncio.to_thread", new=_run_in_thread):
            result = await gateway.approve_usdc(1_000_000)

        assert isinstance(result, TransactionResult)
        assert result.status == "CONFIRMED"
        assert result.gas_used == 21000
        assert result.gas_price_gwei == 50.0

    @pytest.mark.asyncio
    async def test_approve_exchange_builds_and_sends(self) -> None:
        """approve_exchange should build an ERC-1155 approval tx."""
        gateway = _make_patched_gateway()

        mock_contract = MagicMock()
        mock_approve_func = MagicMock()
        mock_approve_func.build_transaction = MagicMock(return_value={"to": "0xExch", "data": "0x"})
        mock_contract.functions.approve.return_value = mock_approve_func
        gateway._w3.eth.contract.return_value = mock_contract

        gateway._w3.to_wei.return_value = 50_000_000_000
        gateway._w3.eth.get_transaction_count.return_value = 5

        gateway._account.sign_transaction.return_value = MagicMock(raw_transaction=b"0xsigned")
        gateway._w3.eth.send_raw_transaction.return_value = b"\xef\x01"
        gateway._w3.eth.wait_for_transaction_receipt.return_value = _make_mock_receipt()

        with patch("asyncio.to_thread", new=_run_in_thread):
            result = await gateway.approve_exchange("0x999", 1)

        assert isinstance(result, TransactionResult)
        assert result.status == "CONFIRMED"

    @pytest.mark.asyncio
    async def test_approve_usdc_build_error_wraps_contract_error(self) -> None:
        """Build failure should be wrapped in ContractError."""
        gateway = _make_patched_gateway()

        mock_contract = MagicMock()
        mock_contract.functions.approve.side_effect = Exception("build failed")
        gateway._w3.eth.contract.return_value = mock_contract

        with pytest.raises(ContractError, match="Failed to build"):
            await gateway.approve_usdc(100)

    @pytest.mark.asyncio
    async def test_insufficient_gas_error(self) -> None:
        """ValueError about insufficient funds raises InsufficientGasError."""
        gateway = _make_patched_gateway()

        mock_contract = MagicMock()
        mock_approve_func = MagicMock()
        mock_approve_func.build_transaction = MagicMock(return_value={"to": "0xCTF"})
        mock_contract.functions.approve.return_value = mock_approve_func
        gateway._w3.eth.contract.return_value = mock_contract
        gateway._w3.to_wei.return_value = 50_000_000_000
        gateway._w3.eth.get_transaction_count.return_value = 5

        # _send_transaction inside approve_usdc will hit ValueError
        def failing_send(*args, **kwargs):
            raise ValueError("insufficient funds for gas")

        gateway._account.sign_transaction.return_value = MagicMock(raw_transaction=b"0x")
        gateway._w3.eth.send_raw_transaction.side_effect = failing_send

        with (
            patch("asyncio.to_thread", new=_run_in_thread),
            pytest.raises(InsufficientGasError, match="MATIC"),
        ):
            await gateway.approve_usdc(100)

    @pytest.mark.asyncio
    async def test_backward_compat_approve(self) -> None:
        """Legacy approve() should delegate to approve_usdc."""
        gateway = _make_patched_gateway()

        mock_contract = MagicMock()
        mock_approve_func = MagicMock()
        mock_approve_func.build_transaction = MagicMock(return_value={"to": "0xCTF"})
        mock_contract.functions.approve.return_value = mock_approve_func
        gateway._w3.eth.contract.return_value = mock_contract
        gateway._w3.to_wei.return_value = 50_000_000_000
        gateway._w3.eth.get_transaction_count.return_value = 5

        gateway._account.sign_transaction.return_value = MagicMock(raw_transaction=b"0x")
        gateway._w3.eth.send_raw_transaction.return_value = b"\xab"
        gateway._w3.eth.wait_for_transaction_receipt.return_value = _make_mock_receipt()

        with patch("asyncio.to_thread", new=_run_in_thread):
            result = await gateway.approve("0xUSDC", "0xspender", 1000.0)

        assert result is True


class TestContractsGatewayLifecycle:
    """Tests for connection lifecycle (close, context manager)."""

    @pytest.mark.asyncio
    async def test_close_releases_resources(self) -> None:
        """close() should set _w3 and _account to None."""
        gateway = _make_patched_gateway()
        assert gateway._w3 is not None
        assert gateway._account is not None

        await gateway.close()

        assert gateway._w3 is None
        assert gateway._account is None

    @pytest.mark.asyncio
    async def test_close_idempotent(self) -> None:
        """Calling close() multiple times should not raise."""
        gateway = ContractsGateway(ContractsConfig())
        await gateway.close()
        await gateway.close()

    @pytest.mark.asyncio
    async def test_context_manager(self) -> None:
        """__aenter__/__aexit__ should not raise."""
        async with ContractsGateway(ContractsConfig()):
            pass

    @pytest.mark.asyncio
    async def test_connect_not_called_raises(self) -> None:
        """Using a gateway without calling connect() should raise RuntimeError."""
        gateway = ContractsGateway(ContractsConfig())

        with pytest.raises(RuntimeError, match="not connected"):
            await gateway.get_onchain_balance("0x1")


class TestContractsGatewayErrors:
    """Tests for error conditions."""

    @pytest.mark.asyncio
    async def test_operation_without_private_key_raises(self) -> None:
        """Operations requiring a private key should raise RuntimeError."""
        gateway = ContractsGateway(ContractsConfig())
        gateway._w3 = MagicMock()

        with pytest.raises(RuntimeError, match="private key"):
            await gateway.approve_usdc(100)

    @pytest.mark.asyncio
    async def test_transaction_failure_wraps_error(self) -> None:
        """Generic ValueError in tx sending should wrap in ContractError."""
        gateway = _make_patched_gateway()

        mock_contract = MagicMock()
        mock_approve_func = MagicMock()
        mock_approve_func.build_transaction = MagicMock(return_value={"to": "0xCTF"})
        mock_contract.functions.approve.return_value = mock_approve_func
        gateway._w3.eth.contract.return_value = mock_contract
        gateway._w3.to_wei.return_value = 50_000_000_000
        gateway._w3.eth.get_transaction_count.return_value = 5

        gateway._account.sign_transaction.return_value = MagicMock(raw_transaction=b"0x")
        gateway._w3.eth.send_raw_transaction.side_effect = ValueError("nonce too low")

        with (
            patch("asyncio.to_thread", new=_run_in_thread),
            pytest.raises(ContractError, match="nonce too low"),
        ):
            await gateway.approve_usdc(100)


class TestContractsGatewayNotImplemented:
    """split / merge / redeem still raise NotImplementedError."""

    @pytest.mark.asyncio
    async def test_split_not_implemented(self) -> None:
        gateway = _make_patched_gateway()
        with pytest.raises(NotImplementedError):
            await gateway.split("0xcond", 100.0)

    @pytest.mark.asyncio
    async def test_merge_not_implemented(self) -> None:
        gateway = _make_patched_gateway()
        with pytest.raises(NotImplementedError):
            await gateway.merge("0xcond", 100.0)

    @pytest.mark.asyncio
    async def test_redeem_not_implemented(self) -> None:
        gateway = _make_patched_gateway()
        with pytest.raises(NotImplementedError):
            await gateway.redeem("0xcond", 0, 100)
