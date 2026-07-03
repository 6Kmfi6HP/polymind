"""
Polymarket smart-contract gateway — split, merge, redeem, balance, approve.

Encapsulates all on-chain interactions (ERC-1155, CTF Exchange, etc.) behind
project-owned domain types.  Strategy code must never call contracts directly;
use this adapter through the IntentExecutor or workflow layer.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Any


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


class ContractsGateway:
    """Gateway for Polymarket on-chain operations.

    Subclasses should override split, merge, redeem, balance_of, and approve.
    Base implementation raises NotImplementedError on all operations.
    """

    def __init__(self, config: ContractsConfig) -> None:
        self.config = config

    async def __aenter__(self) -> ContractsGateway:
        return self

    async def __aexit__(self, *args: Any) -> None:
        await self.close()

    async def split(
        self, market_id: str, outcome: str, amount: float
    ) -> SplitResult:
        """Split parent tokens into outcome A and B tokens."""
        raise NotImplementedError

    async def merge(
        self, market_id: str, outcome_a: str, outcome_b: str
    ) -> MergeResult:
        """Merge outcome A and B tokens back into parent tokens."""
        raise NotImplementedError

    async def redeem(self, market_id: str, outcome: str) -> RedeemResult:
        """Redeem winning tokens for USDC after resolution."""
        raise NotImplementedError

    async def balance_of(
        self, owner: str, token_id: str
    ) -> float:
        """Check ERC-1155 token balance for an owner."""
        raise NotImplementedError

    async def approve(
        self, token_address: str, spender: str, amount: float
    ) -> bool:
        """Approve a spender to transfer tokens on behalf of the owner."""
        raise NotImplementedError

    async def close(self) -> None:
        """Release any web3 provider resources."""
        pass
