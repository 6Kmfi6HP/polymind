"""
Tests for Signer authentication.
"""

from __future__ import annotations

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
        creds = WalletCredentials(private_key="0xabc123")
        assert "abc123" in creds.address


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
        assert "WALLET" in repr(Signer.from_wallet("0xabc"))
        assert "API_KEY" in repr(Signer.from_api_key("k", "s", "p"))
