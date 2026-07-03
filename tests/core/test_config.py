"""
Tests for configuration management.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

from polymind.core.config import Config, RiskLimits, load_config, save_config


class TestRiskLimits:
    def test_defaults(self):
        limits = RiskLimits()
        assert limits.max_position_size == 50.0
        assert limits.max_total_exposure == 500.0
        assert limits.max_daily_loss == 100.0
        assert limits.kelly_fraction == 0.25


class TestConfig:
    def test_defaults(self):
        cfg = Config()
        assert cfg.initial_capital == 1000.0
        assert cfg.dry_run is True
        assert cfg.is_configured is False
        assert cfg.platform == "polymarket"

    def test_has_wallet_with_key(self):
        cfg = Config(private_key="0xabc123")
        assert cfg.has_wallet() is True

    def test_has_wallet_without_key(self):
        cfg = Config()
        assert cfg.has_wallet() is False

    def test_get_available_agents(self):
        cfg = Config(
            anthropic_api_key="sk-ant-xxx",
            openai_api_key="sk-openai-xxx",
        )
        agents = cfg.get_available_agents()
        assert "anthropic" in agents
        assert "openai" in agents
        assert "google" not in agents

    def test_no_agents(self):
        cfg = Config()
        assert cfg.get_available_agents() == []


class TestLoadConfig:
    def test_default_config_no_env(self):
        """With no env vars, should return defaults."""
        cfg = load_config()
        assert isinstance(cfg, Config)
        assert cfg.initial_capital == 1000.0

    def test_env_vars_override(self):
        """Environment variables should override defaults."""
        os.environ["ANTHROPIC_API_KEY"] = "sk-test-key"
        os.environ["INITIAL_CAPITAL"] = "5000"
        os.environ["PRIVATE_KEY"] = "0xwallettest"
        try:
            cfg = load_config()
            assert cfg.anthropic_api_key == "sk-test-key"
            assert cfg.initial_capital == 5000.0
            assert cfg.has_wallet() is True
            assert cfg.is_configured is True
        finally:
            del os.environ["ANTHROPIC_API_KEY"]
            del os.environ["INITIAL_CAPITAL"]
            del os.environ["PRIVATE_KEY"]

    def test_save_and_load_roundtrip(self):
        """save_config then load should preserve dry_run setting."""
        from polymind.core.config import CONFIG_DIR, CONFIG_FILE

        with tempfile.TemporaryDirectory() as tmp:
            orig_dir = CONFIG_DIR
            orig_file = CONFIG_FILE
            try:
                import polymind.core.config as cfg_mod

                cfg_mod.CONFIG_DIR = Path(tmp)
                cfg_mod.CONFIG_FILE = Path(tmp) / "config.yaml"

                cfg = Config(dry_run=False)
                save_config(cfg)

                # Reset singleton and reload
                cfg_mod._config = None
                reloaded = cfg_mod.load_config()
                assert reloaded.dry_run is False
            finally:
                cfg_mod.CONFIG_DIR = orig_dir
                cfg_mod.CONFIG_FILE = orig_file
