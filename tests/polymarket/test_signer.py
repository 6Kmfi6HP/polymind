"""
Tests for Signer authentication and signing operations.
"""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from polymind.polymarket.errors import InsufficientAuthError
from polymind.polymarket.signer import ApiKeyCredentials, AuthTier, Signer, WalletCredentials


class TestAuthTier:
    def test_values_distinct(self):
        assert AuthTier.PUBLIC != AuthTier.API_KEY
        assert AuthTier.API_KEY != AuthTier.WALLET


class TestApiKeyCredentials:
    def test_construction(self):
        creds = ApiKeyCredentials(api_key="key123", api_secret="secret456", api_passphrase="phrase")
        assert creds.api_key == "key123"
        assert creds.api_secret == "secret456"

    def test_repr_masks_key(self):
        creds = ApiKeyCredentials(api_key="k" * 20, api_secret="s", api_passphrase="p")
        r = repr(creds)
        assert "kkkkkkkk" in r
        assert "k" * 20 not in r


class TestWalletCredentials:
    def test_address_property(self):
        """With a mock, address returns a checksummed address."""
        creds = WalletCredentials(private_key="0x" + "ab" * 32)  # 64 hex chars
        addr = creds.address
        assert addr.startswith("0x")
        assert len(addr) == 42

    def test_address_is_derived_from_key(self):
        """Known private key produces known address."""
        creds = WalletCredentials(
            private_key="0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80"
        )
        assert creds.address == "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266"

    # ── Coverage: WalletCredentials.__repr__ (line 58) ──

    def test_wallet_credentials_repr(self):
        creds = WalletCredentials(private_key="0x" + "ab" * 32)
        r = repr(creds)
        assert r.startswith("WalletCredentials(address='0x")
        assert creds.address in r


class TestSigner:
    def test_public_tier(self):
        s = Signer.public()
        assert s.tier == AuthTier.PUBLIC
        assert s.can_sign is False
        assert s.can_authenticate is False

    def test_api_key_tier(self):
        s = Signer.from_api_key("k", "s", "p")
        assert s.tier == AuthTier.API_KEY
        assert s.can_sign is False
        assert s.can_authenticate is True
        assert s.api_creds is not None

    def test_wallet_tier(self):
        s = Signer.from_wallet("0xprivkey")
        assert s.tier == AuthTier.WALLET
        assert s.can_sign is True
        assert s.can_authenticate is True
        assert s.wallet_creds is not None

    def test_repr(self):
        assert "PUBLIC" in repr(Signer.public())
        assert "API_KEY" in repr(Signer.from_api_key("k", "s", "p"))

    # ── Coverage: Signer.__repr__ with wallet tier (line 162) ──

    def test_repr_wallet_tier(self):
        s = Signer.from_wallet("0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80")
        r = repr(s)
        assert "WALLET" in r
        assert "0xf39Fd6e51aad88F6F4ce6aB8827279cffFb92266" in r

    # ── sign_typed_data ──────────────────────────────────────────────────

    def test_sign_typed_data_raises_for_public(self):
        s = Signer.public()
        with pytest.raises(InsufficientAuthError):
            s.sign_typed_data({}, {}, {})

    def test_sign_typed_data_raises_for_api_key(self):
        s = Signer.from_api_key("k", "s", "p")
        with pytest.raises(InsufficientAuthError):
            s.sign_typed_data({}, {}, {})

    def test_sign_typed_data_returns_hex(self):
        """Real EIP-712 signing with a known private key (no network)."""
        s = Signer.from_wallet("0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80")
        result = s.sign_typed_data(
            {"name": "test", "version": "1"},
            {"Message": [{"name": "value", "type": "string"}]},
            {"value": "hello"},
        )
        assert result.startswith("0x")
        assert len(result) == 132  # 65 bytes * 2 hex chars + 0x

        s = Signer.from_wallet("0x" + "ab" * 32)
        result = s.sign_typed_data(
            {"name": "test", "version": "1"},
            {"Message": [{"name": "value", "type": "string"}]},
            {"value": "hello"},
        )
        assert result.startswith("0x")

    # ── sign_hash ────────────────────────────────────────────────────────

    def test_sign_hash_raises_for_public(self):
        s = Signer.public()
        with pytest.raises(InsufficientAuthError):
            s.sign_hash(b"test")

    def test_sign_hash_returns_hex(self):
        """Real hash signing with a known private key (no network)."""
        s = Signer.from_wallet("0xac0974bec39a17e36ba4a6b4d238ff944bacb478cbed5efcae784d7bf4f2ff80")
        result = s.sign_hash(b"\x00" * 32)  # 32-byte hash
        assert result.startswith("0x")
        assert len(result) == 132  # 65 bytes * 2 hex chars + 0x

        s = Signer.from_wallet("0x" + "ab" * 32)
        result = s.sign_hash(b"\x01" * 32)
        assert result.startswith("0x")

    # ── derive_api_key ──────────────────────────────────────────────────

    def test_derive_api_key_raises_for_public(self):
        s = Signer.public()
        with pytest.raises(InsufficientAuthError):
            s.derive_api_key("https://clob.polymarket.com")

    def test_derive_api_key_returns_creds(self):
        s = Signer.from_wallet("0x" + "ab" * 32)
        with patch("polymind.polymarket.signer.ClobClient") as mock_cls:
            mock_instance = MagicMock()
            mock_creds = MagicMock()
            mock_creds.api_key = "derived-key"
            mock_creds.api_secret = "derived-secret"
            mock_creds.api_passphrase = "derived-phrase"
            mock_instance.create_or_derive_api_creds.return_value = mock_creds
            mock_cls.return_value = mock_instance

            result = s.derive_api_key("https://clob.polymarket.com")

        assert isinstance(result, ApiKeyCredentials)
        assert result.api_key == "derived-key"
