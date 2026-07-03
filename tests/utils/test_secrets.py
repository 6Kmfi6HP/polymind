"""
Tests for polymind.utils.secrets.
"""

from __future__ import annotations

import os

import pytest

from polymind.utils.secrets import SecretNotFound, SecretsManager, mask


class TestMask:
    def test_normal(self):
        assert mask("abcdefghijklmnop") == "abcdef...mnop"

    def test_short_string(self):
        """Shows fewer characters when the string is short."""
        assert mask("abc", keep_first=1, keep_last=1) == "a...c"

    def test_empty(self):
        assert mask("") == ""

    def test_default_keep_shorter_than_total(self):
        """String exactly keep_first+keep_last long is returned unchanged."""
        assert mask("1234567890") == "1234567890"
        assert mask("123456789") == "123456789"

    def test_keep_first_and_last_custom(self):
        assert mask("abcdefghij", keep_first=2, keep_last=2) == "ab...ij"


class TestSecretsManager:
    def test_default_prefix(self):
        mgr = SecretsManager()
        assert mgr._prefix == "POLYMIND"

    def test_custom_prefix(self):
        mgr = SecretsManager(env_prefix="MYAPP_")
        assert mgr._prefix == "MYAPP"

    def test_prefix_stripped_and_uppercased(self):
        mgr = SecretsManager(env_prefix="  my_app_  ")
        assert mgr._prefix == "MY_APP"

    def test_get_returns_none_when_missing(self):
        mgr = SecretsManager("UNSET_PREFIX_XYZ_")
        assert mgr.get("SOMETHING") is None

    def test_get_returns_value_when_set(self, monkeypatch):
        monkeypatch.setenv("POLYMIND_ANTHROPIC_API_KEY", "sk-ant-12345")
        mgr = SecretsManager("POLYMIND_")
        assert mgr.get("ANTHROPIC_API_KEY") == "sk-ant-12345"

    def test_get_or_raise_returns_value(self, monkeypatch):
        monkeypatch.setenv("POLYMIND_WALLET_PK", "0xdeadbeef")
        mgr = SecretsManager("POLYMIND_")
        assert mgr.get_or_raise("WALLET_PK") == "0xdeadbeef"

    def test_get_or_raise_raises_secret_not_found(self):
        mgr = SecretsManager("POLYMIND_")
        with pytest.raises(SecretNotFound):
            mgr.get_or_raise("DOES_NOT_EXIST")

    def test_different_prefix_uses_correct_env_var(self, monkeypatch):
        monkeypatch.setenv("FOO_API_KEY", "sk-foo-999")
        mgr = SecretsManager("FOO_")
        assert mgr.get("API_KEY") == "sk-foo-999"

    def test_different_prefix_does_not_read_default(self, monkeypatch):
        monkeypatch.setenv("POLYMIND_API_KEY", "default-val")
        monkeypatch.setenv("BAR_API_KEY", "bar-val")
        mgr = SecretsManager("BAR_")
        assert mgr.get("API_KEY") == "bar-val"
