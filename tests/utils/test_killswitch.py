"""
Tests for polymind.utils.killswitch.
"""

from __future__ import annotations

import os

import pytest

from polymind.utils.killswitch import KillSwitch


class TestKillSwitchDefault:
    """Tests with default constructor arguments (no file path)."""

    def test_default_not_triggered(self):
        ks = KillSwitch()
        assert ks.is_triggered() is False

    def test_trigger_sets_internal_flag(self):
        ks = KillSwitch()
        ks.trigger()
        assert ks.is_triggered() is True

    def test_release_clears_flag(self):
        ks = KillSwitch()
        ks.trigger()
        assert ks.is_triggered() is True
        ks.release()
        assert ks.is_triggered() is False

    def test_release_when_not_triggered_does_not_raise(self):
        ks = KillSwitch()
        ks.release()  # should not raise


class TestKillSwitchFileBased:
    """Tests using a sentinel file."""

    def test_default_not_triggered(self, tmp_path):
        sentinel = tmp_path / ".kill"
        ks = KillSwitch(file_path=str(sentinel))
        assert ks.is_triggered() is False

    def test_trigger_via_file_path(self, tmp_path):
        sentinel = tmp_path / ".kill"
        ks = KillSwitch(file_path=str(sentinel))
        ks.trigger()
        assert sentinel.exists()
        assert ks.is_triggered() is True

    def test_release_removes_file(self, tmp_path):
        sentinel = tmp_path / ".kill"
        ks = KillSwitch(file_path=str(sentinel))
        ks.trigger()
        assert sentinel.exists()
        ks.release()
        assert not sentinel.exists()
        assert ks.is_triggered() is False

    def test_release_when_no_file_does_not_raise(self, tmp_path):
        sentinel = tmp_path / ".kill"
        ks = KillSwitch(file_path=str(sentinel))
        ks.release()  # should not raise

    def test_trigger_with_nested_directory(self, tmp_path):
        sentinel = tmp_path / "sub" / "nested" / ".kill"
        ks = KillSwitch(file_path=str(sentinel))
        ks.trigger()
        assert sentinel.exists()

    def test_trigger_after_release(self, tmp_path):
        sentinel = tmp_path / ".kill"
        ks = KillSwitch(file_path=str(sentinel))
        ks.trigger()
        assert sentinel.exists()
        ks.release()
        assert not sentinel.exists()
        ks.trigger()
        assert sentinel.exists()

    def test_triggered_when_file_exists(self, tmp_path):
        sentinel = tmp_path / ".kill"
        sentinel.touch()
        ks = KillSwitch(file_path=str(sentinel))
        assert ks.is_triggered() is True


class TestKillSwitchEnvBased:
    """Tests using an environment variable."""

    def test_env_var_triggers(self, monkeypatch):
        monkeypatch.setenv("POLYMIND_KILL", "1")
        ks = KillSwitch()
        assert ks.is_triggered() is True

    def test_env_var_true_triggers(self, monkeypatch):
        monkeypatch.setenv("POLYMIND_KILL", "true")
        ks = KillSwitch()
        assert ks.is_triggered() is True

    def test_env_var_TRUE_triggers(self, monkeypatch):
        monkeypatch.setenv("POLYMIND_KILL", "TRUE")
        ks = KillSwitch()
        assert ks.is_triggered() is True

    def test_env_var_0_does_not_trigger(self, monkeypatch):
        monkeypatch.setenv("POLYMIND_KILL", "0")
        ks = KillSwitch()
        assert ks.is_triggered() is False

    def test_env_var_false_does_not_trigger(self, monkeypatch):
        monkeypatch.setenv("POLYMIND_KILL", "false")
        ks = KillSwitch()
        assert ks.is_triggered() is False

    def test_env_var_empty_does_not_trigger(self, monkeypatch):
        monkeypatch.setenv("POLYMIND_KILL", "")
        ks = KillSwitch()
        assert ks.is_triggered() is False

    def test_custom_env_var_triggered(self, monkeypatch):
        monkeypatch.setenv("MY_CUSTOM_KILL", "1")
        ks = KillSwitch(env_var="MY_CUSTOM_KILL")
        assert ks.is_triggered() is True


class TestKillSwitchPrecedence:
    """Tests for precedence (file path takes precedence)."""

    def test_file_path_takes_precedence(self, monkeypatch, tmp_path):
        """File existence returns True even if env var says 'not triggered'."""
        sentinel = tmp_path / ".kill"
        sentinel.touch()
        monkeypatch.setenv("POLYMIND_KILL", "0")
        ks = KillSwitch(file_path=str(sentinel))
        assert ks.is_triggered() is True

    def test_env_var_still_checked_when_no_file(self, monkeypatch):
        """Without a file path, only the env var and flag matter."""
        monkeypatch.setenv("POLYMIND_KILL", "1")
        ks = KillSwitch()
        assert ks.is_triggered() is True

    def test_file_missing_but_env_set_triggers(self, monkeypatch, tmp_path):
        """If file is missing but env var is set, still triggered."""
        sentinel = tmp_path / ".kill"
        monkeypatch.setenv("POLYMIND_KILL", "1")
        ks = KillSwitch(file_path=str(sentinel))
        assert ks.is_triggered() is True
