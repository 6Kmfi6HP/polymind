"""
Authentication credentials and signing for Polymarket API access.

Encapsulates the three auth tiers (PUBLIC, API_KEY, WALLET) as defined
in ADR 0003 / ADR 0004.  The Signer holds credentials for one tier and
provides signing operations for wallet-tier access.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum, auto
from typing import Any

from py_clob_client.client import ClobClient

from polymind.polymarket.errors import InsufficientAuthError


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
    _address: str | None = None

    @property
    def address(self) -> str:
        """Return the checksummed Ethereum address derived from private_key."""
        if self._address is None:
            from eth_account import Account

            acct = Account.from_key(self.private_key)
            object.__setattr__(self, "_address", acct.address)
        return self._address  # type: ignore[return-value]

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
        api_creds: ApiKeyCredentials | None = None,
        wallet_creds: WalletCredentials | None = None,
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

    def sign_typed_data(
        self, domain: dict[str, Any], message_types: dict[str, Any], message: dict[str, Any]
    ) -> str:
        """Sign an EIP-712 typed data payload with the wallet private key.

        Returns the hex-encoded signature (0x-prefixed).
        Raises ``InsufficientAuthError`` if tier < WALLET.
        """
        if self.tier != AuthTier.WALLET or self.wallet_creds is None:
            raise InsufficientAuthError("EIP-712 signing requires wallet-tier signer")

        from eth_account import Account
        from eth_account.messages import encode_typed_data

        encoded = encode_typed_data(domain, message_types, message)
        signed = Account.sign_message(encoded, self.wallet_creds.private_key)
        return "0x" + signed.signature.hex()

    def sign_hash(self, message_hash: bytes) -> str:
        """Sign an arbitrary hash with the wallet private key.

        Used for on-chain contract interactions.
        Raises ``InsufficientAuthError`` if tier < WALLET.
        """
        if self.tier != AuthTier.WALLET or self.wallet_creds is None:
            raise InsufficientAuthError("Hash signing requires wallet-tier signer")

        from eth_account import Account

        signed = Account.unsafe_sign_hash(message_hash, self.wallet_creds.private_key)
        return "0x" + signed.signature.hex()

    def derive_api_key(self, host: str, chain_id: int | None = None) -> ApiKeyCredentials:
        """Derive (or re-derive) API key credentials from the wallet.

        This wraps the SDK's ``ClobClient.create_or_derive_api_creds``
        flow.  Raises ``InsufficientAuthError`` if tier < WALLET.
        """
        if self.tier != AuthTier.WALLET or self.wallet_creds is None:
            raise InsufficientAuthError("API key derivation requires wallet-tier signer")

        client = ClobClient(host=host, chain_id=chain_id or 137, key=self.wallet_creds.private_key)
        creds = client.create_or_derive_api_creds()
        return ApiKeyCredentials(
            api_key=creds.api_key,  # type: ignore[union-attr]
            api_secret=creds.api_secret,  # type: ignore[union-attr]
            api_passphrase=creds.api_passphrase,  # type: ignore[union-attr]
        )

    def __repr__(self) -> str:
        if self.tier == AuthTier.WALLET and self.wallet_creds:
            return f"Signer({self.tier.name}, wallet={self.wallet_creds.address})"
        if self.tier == AuthTier.API_KEY and self.api_creds:
            return f"Signer({self.tier.name}, key={self.api_creds.api_key[:8]}...)"
        return f"Signer({self.tier.name})"
