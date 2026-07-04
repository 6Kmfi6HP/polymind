"""
Polymarket smart-contract gateway — split, merge, redeem, balance, approve.

Encapsulates all on-chain interactions (ERC-1155, CTF Exchange, etc.) behind
project-owned domain types.  Strategy code must never call contracts directly;
use this adapter through the IntentExecutor or workflow layer.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from datetime import datetime
from typing import Any

import eth_account
from web3 import Web3

from polymind.polymarket.errors import ContractError, InsufficientGasError

# ── Domain types ──────────────────────────────────────────────────────────


@dataclass
class OnChainBalance:
    """Combined ERC-1155 token balance + USDC balance for an account."""

    token_id: str
    balance: int
    usdc_balance: float
    decimals: int = 6


@dataclass
class TransactionResult:
    """Outcome of a submitted on-chain transaction."""

    tx_hash: str
    status: str
    block_number: int
    gas_used: int
    gas_price_gwei: float


@dataclass
class SplitResult:
    """Outcome of a token split operation."""

    tx_hash: str
    outcome_a_amount: float = 0.0
    outcome_b_amount: float = 0.0
    timestamp: datetime | None = None


@dataclass
class MergeResult:
    """Outcome of a token merge operation."""

    tx_hash: str
    outcome_a_amount: float = 0.0
    outcome_b_amount: float = 0.0
    timestamp: datetime | None = None


@dataclass
class RedeemResult:
    """Outcome of redeeming winning tokens after market resolution."""

    tx_hash: str
    proceeds_usdc: float = 0.0
    timestamp: datetime | None = None


@dataclass
class TokenBalance:
    """ERC-1155 token balance for a single token ID."""

    token_id: str
    owner: str
    balance: float


@dataclass
class ContractsConfig:
    """Configuration for the on-chain contracts gateway."""

    rpc_url: str = "https://polygon-rpc.com"
    private_key: str | None = None
    chain_id: int = 137
    gas_limit: int = 500_000
    gas_price_gwei: float = 50.0


# ── Contract addresses (Polygon mainnet) ──────────────────────────────────
USDC_ADDRESS = "0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174"
CTF_EXCHANGE_ADDRESS = "0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8Bd8987"

# Minimal ERC-1155 ABI for balanceOf
ERC1155_ABI = [
    {
        "constant": True,
        "inputs": [
            {"name": "_owner", "type": "address"},
            {"name": "_id", "type": "uint256"},
        ],
        "name": "balanceOf",
        "outputs": [{"name": "", "type": "uint256"}],
        "type": "function",
    }
]

# Minimal ERC-20 ABI for USDC balance and approve
ERC20_ABI = [
    {
        "constant": True,
        "inputs": [{"name": "_owner", "type": "address"}],
        "name": "balanceOf",
        "outputs": [{"name": "", "type": "uint256"}],
        "type": "function",
    },
    {
        "constant": False,
        "inputs": [
            {"name": "_spender", "type": "address"},
            {"name": "_amount", "type": "uint256"},
        ],
        "name": "approve",
        "outputs": [{"name": "", "type": "bool"}],
        "type": "function",
    },
]


class ContractsGateway:
    """Gateway for Polymarket on-chain operations.

    Wraps Web3.py to interact with Polymarket smart contracts (CTF Exchange,
    USDC) on Polygon.  All blocking Web3 calls are dispatched via
    ``asyncio.to_thread`` so they do not block the event loop.

    Subclasses may still override ``split``, ``merge`` and ``redeem`` for
    testing or alternative implementations; the base implementation raises
    ``NotImplementedError`` for those three.
    """

    def __init__(self, config: ContractsConfig) -> None:
        self.config = config
        self._w3: Any = None
        self._account: Any = None

    async def __aenter__(self) -> ContractsGateway:
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()

    # ── Connection lifecycle ──────────────────────────────────────────────

    async def connect(self) -> None:
        """Initialise Web3 provider and (optionally) load the private key."""
        provider = Web3(Web3.HTTPProvider(self.config.rpc_url))
        self._w3 = provider
        if self.config.private_key:
            self._account = eth_account.Account.from_key(self.config.private_key)

    async def close(self) -> None:
        """Release Web3 provider resources."""
        self._w3 = None
        self._account = None

    # ── Balance queries ───────────────────────────────────────────────────

    async def get_onchain_balance(self, token_id: str) -> OnChainBalance:
        """Return the ERC-1155 token balance + USDC balance for the connected account."""
        w3 = self._require_w3()
        if not self._account:
            return OnChainBalance(token_id=token_id, balance=0, usdc_balance=0.0)

        try:
            # ERC-1155 balance via CTF Exchange contract
            token_contract = w3.eth.contract(
                address=Web3.to_checksum_address(CTF_EXCHANGE_ADDRESS), abi=ERC1155_ABI
            )
            balance = await asyncio.to_thread(
                token_contract.functions.balanceOf(self._account.address, int(token_id, 16)).call
            )

            # USDC balance
            usdc_contract = w3.eth.contract(
                address=Web3.to_checksum_address(USDC_ADDRESS), abi=ERC20_ABI
            )
            usdc_raw = await asyncio.to_thread(
                usdc_contract.functions.balanceOf(self._account.address).call
            )

            return OnChainBalance(
                token_id=token_id,
                balance=balance,
                usdc_balance=usdc_raw / 1e6,
            )
        except Exception as exc:
            raise ContractError(
                f"Failed to fetch on-chain balance for token {token_id}: {exc}"
            ) from exc

    async def balance_of(self, owner: str, token_id: str) -> float:
        """Backward-compat: return raw ERC-1155 balance as float.

        .. note::
            The *owner* parameter is ignored — the connected account's balance
            is always returned.  Kept for backward compatibility.
        """
        bal = await self.get_onchain_balance(token_id)
        return float(bal.balance)

    # ── On-chain operations ───────────────────────────────────────────────

    async def split(
        self, condition_id: str, amount: float, outcomes: list | None = None
    ) -> SplitResult:
        """Split parent collateral into outcome tokens.

        .. note::
            Not yet implemented in the base gateway.
        """
        raise NotImplementedError

    async def merge(
        self, condition_id: str, amount: float, outcomes: list | None = None
    ) -> MergeResult:
        """Merge outcome tokens back into parent collateral.

        .. note::
            Not yet implemented in the base gateway.
        """
        raise NotImplementedError

    async def redeem(self, condition_id: str, outcome_index: int, amount: int) -> RedeemResult:
        """Redeem winning outcome tokens for USDC after market resolution.

        .. note::
            Not yet implemented in the base gateway.
        """
        raise NotImplementedError

    # ── Approvals ─────────────────────────────────────────────────────────

    async def approve_usdc(self, amount: int) -> TransactionResult:
        """Approve the CTF Exchange to spend *amount* USDC (6 decimals)."""
        self._require_account()
        w3 = self._require_w3()

        usdc = w3.eth.contract(address=Web3.to_checksum_address(USDC_ADDRESS), abi=ERC20_ABI)
        try:
            tx = await asyncio.to_thread(
                usdc.functions.approve(
                    Web3.to_checksum_address(CTF_EXCHANGE_ADDRESS), amount
                ).build_transaction,
                self._build_tx_params(),
            )
        except Exception as exc:
            raise ContractError(f"Failed to build approve_usdc transaction: {exc}") from exc

        return await self._send_transaction(tx)

    async def approve_exchange(self, token_id: str, amount: int) -> TransactionResult:
        """Approve the CTF Exchange to transfer ERC-1155 tokens on our behalf."""
        self._require_account()
        w3 = self._require_w3()

        exchange = w3.eth.contract(
            address=Web3.to_checksum_address(CTF_EXCHANGE_ADDRESS), abi=ERC1155_ABI
        )
        try:
            tx = await asyncio.to_thread(
                exchange.functions.approve(
                    Web3.to_checksum_address(CTF_EXCHANGE_ADDRESS), amount
                ).build_transaction,
                self._build_tx_params(),
            )
        except Exception as exc:
            raise ContractError(f"Failed to build approve_exchange transaction: {exc}") from exc

        return await self._send_transaction(tx)

    async def approve(self, token_address: str, spender: str, amount: float) -> bool:
        """Legacy approve — delegates to ``approve_usdc``.

        Returns ``True`` if the transaction was confirmed.
        """
        result = await self.approve_usdc(int(amount))
        return result.status == "CONFIRMED"

    # ── Internal helpers ──────────────────────────────────────────────────

    def _require_w3(self) -> Any:
        """Return the Web3 instance or raise if not connected."""
        if self._w3 is None:
            raise RuntimeError("Gateway not connected. Call connect() first.")
        return self._w3

    def _require_account(self) -> None:
        """Raise if no private key is configured."""
        if not self._account:
            raise RuntimeError("On-chain operations require a private key in ContractsConfig.")

    def _build_tx_params(self) -> dict:
        """Build the standard transaction parameter dict."""
        w3 = self._w3
        return {
            "from": self._account.address,
            "gas": self.config.gas_limit,
            "gasPrice": w3.to_wei(self.config.gas_price_gwei, "gwei"),
            "nonce": w3.eth.get_transaction_count(self._account.address),
            "chainId": self.config.chain_id,
        }

    async def _send_transaction(self, tx: dict) -> TransactionResult:
        """Sign, send and wait for a transaction receipt.

        Raises ``InsufficientGasError`` on known gas-related failures and
        ``ContractError`` for all other on-chain errors.
        """
        try:
            signed = self._account.sign_transaction(tx)
            tx_hash = await asyncio.to_thread(
                self._w3.eth.send_raw_transaction, signed.raw_transaction
            )
            receipt = await asyncio.to_thread(self._w3.eth.wait_for_transaction_receipt, tx_hash)
        except ValueError as exc:
            msg = str(exc)
            if "insufficient funds" in msg.lower():
                raise InsufficientGasError(f"Wallet lacks MATIC for gas: {exc}") from exc
            raise ContractError(f"Transaction failed: {exc}") from exc
        except Exception as exc:
            raise ContractError(f"Transaction failed: {exc}") from exc

        tx_hash_str = (
            receipt.transactionHash.hex()
            if hasattr(receipt.transactionHash, "hex")
            else receipt.transactionHash
        )
        return TransactionResult(
            tx_hash=tx_hash_str,
            status="CONFIRMED" if receipt.status == 1 else "FAILED",
            block_number=receipt.blockNumber,
            gas_used=receipt.gasUsed,
            gas_price_gwei=self.config.gas_price_gwei,
        )
