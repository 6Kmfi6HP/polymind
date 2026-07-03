"""
Authentication credentials and signing for Polymarket API access.

Encapsulates the three auth tiers (PUBLIC, API_KEY, WALLET) as defined
in ADR 0003 / ADR 0004.  The Signer holds credentials for one tier and
provides signing operations for wallet-tier access.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import Optional


class AuthTier(Enum):
    """Authentication level for Polymarket API access."""

    PUBLIC = auto()
    API_KEY = auto()
    WALLET = auto()


@dataclass(frozen=True)
class ApiKeyCredentials:
    """API-key-level credentials for L2 authenticated endpoints."""

    api_key: str
    api_secret: str
    api_passphrase: str

    def __repr__(self) -> str:
        return f"ApiKeyCredentials(api_key='{self.api_key[:8]}...')"


@dataclass(frozen=True)
class WalletCredentials:
    """Wallet-level credentials for on-chain operations."""

    private_key: str

    @property
    def address(self) -> str:
        """Return the checksummed Ethereum address (placeholder)."""
        return f"0x...{self.private_key[-6:]}"

    def __repr__(self) -> str:
        return f"WalletCredentials(address='{self.address}')"


class Signer:
    """Holds credentials for one auth tier and provides signing operations.

    The Signer is immutable after construction.  Check ``tier`` to
    determine which operations are available.
    """

    def __init__(
        self,
        tier: AuthTier,
        api_creds: Optional[ApiKeyCredentials] = None,
        wallet_creds: Optional[WalletCredentials] = None,
    ):
        self.tier = tier
        self.api_creds = api_creds
        self.wallet_creds = wallet_creds

    @classmethod
    def public(cls) -> Signer:
        """Create a public-tier Signer (no credentials needed)."""
        return cls(tier=AuthTier.PUBLIC)

    @classmethod
    def from_api_key(cls, api_key: str, secret: str, passphrase: str) -> Signer:
        """Create an API-key-tier Signer."""
        return cls(
            tier=AuthTier.API_KEY,
            api_creds=ApiKeyCredentials(
                api_key=api_key, api_secret=secret, api_passphrase=passphrase
            ),
        )

    @classmethod
    def from_wallet(cls, private_key: str) -> Signer:
        """Create a wallet-tier Signer (implies API-key + on-chain access)."""
        return cls(
            tier=AuthTier.WALLET,
            wallet_creds=WalletCredentials(private_key=private_key),
        )

    @property
    def can_sign(self) -> bool:
        """True if this signer can perform EIP-712 signing (tier >= WALLET)."""
        return self.tier == AuthTier.WALLET

    @property
    def can_authenticate(self) -> bool:
        """True if this signer can authenticate to L2 endpoints (tier >= API_KEY)."""
        return self.tier in (AuthTier.API_KEY, AuthTier.WALLET)

    def __repr__(self) -> str:
        if self.tier == AuthTier.WALLET and self.wallet_creds:
            return f"Signer({self.tier.name}, wallet={self.wallet_creds.address})"
        if self.tier == AuthTier.API_KEY and self.api_creds:
            return f"Signer({self.tier.name}, key={self.api_creds.api_key[:8]}...)"
        return f"Signer({self.tier.name})"
