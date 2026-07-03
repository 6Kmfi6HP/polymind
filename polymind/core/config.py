"""
Configuration management for Polymind.

Priority: environment variables > .env file > ~/.polymind/config.yaml
"""

import os
from dataclasses import dataclass, field
from pathlib import Path

import yaml
from dotenv import load_dotenv

CONFIG_DIR = Path.home() / ".polymind"
CONFIG_FILE = CONFIG_DIR / "config.yaml"


@dataclass
class RiskLimits:
    """Risk management limits."""
    max_position_size: float = 50.0
    max_total_exposure: float = 500.0
    max_daily_loss: float = 100.0
    kelly_fraction: float = 0.25


@dataclass
class Config:
    """Main configuration."""
    # AI
    anthropic_api_key: str | None = None
    openai_api_key: str | None = None
    google_api_key: str | None = None
    preferred_agent: str = "auto"

    # Wallet
    private_key: str | None = None
    platform: str = "polymarket"

    # Trading
    initial_capital: float = 1000.0
    dry_run: bool = True

    # Risk
    risk: RiskLimits = field(default_factory=RiskLimits)

    # State
    is_configured: bool = False

    def has_wallet(self) -> bool:
        return bool(self.private_key)

    def get_available_agents(self) -> list:
        agents = []
        if self.anthropic_api_key:
            agents.append("anthropic")
        if self.openai_api_key:
            agents.append("openai")
        if self.google_api_key:
            agents.append("google")
        return agents


# Global singleton
_config: Config | None = None


def get_config() -> Config:
    global _config
    if _config is None:
        _config = load_config()
    return _config


def load_config() -> Config:
    """Load config from all sources."""
    config = Config()

    load_dotenv()

    # Environment variables
    config.anthropic_api_key = os.getenv("ANTHROPIC_API_KEY")
    config.openai_api_key = os.getenv("OPENAI_API_KEY")
    config.google_api_key = os.getenv("GOOGLE_API_KEY")
    config.private_key = os.getenv("PRIVATE_KEY")

    if os.getenv("INITIAL_CAPITAL"):
        config.initial_capital = float(os.getenv("INITIAL_CAPITAL"))

    if os.getenv("MAX_POSITION_SIZE"):
        config.risk.max_position_size = float(os.getenv("MAX_POSITION_SIZE"))

    # User config file
    if CONFIG_FILE.exists():
        with open(CONFIG_FILE) as f:
            data = yaml.safe_load(f) or {}
        config.dry_run = data.get("trading", {}).get("dry_run", config.dry_run)

    config.is_configured = len(config.get_available_agents()) > 0
    return config


def save_config(config: Config) -> None:
    """Save config to file."""
    CONFIG_DIR.mkdir(parents=True, exist_ok=True)
    with open(CONFIG_FILE, "w") as f:
        yaml.dump({"trading": {"dry_run": config.dry_run}}, f)
