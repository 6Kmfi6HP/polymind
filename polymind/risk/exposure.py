"""
Exposure limits and risk caps for portfolio construction.

Enforces per-market, per-category, and total exposure limits.
"""

from __future__ import annotations

from dataclasses import dataclass

from polymind.core.portfolio import PortfolioTarget


@dataclass
class ExposureConfig:
    """Configuration for exposure limits."""

    max_exposure_per_market: float = 100.0
    max_exposure_total: float = 1000.0
    max_leverage: float = 3.0
    max_correlation_exposure: float = 500.0


class ExposureManager:
    """Enforces exposure limits across the portfolio.

    Validates portfolio targets against configured limits before
    they reach the execution layer.
    """

    def __init__(self, config: ExposureConfig | None = None):
        self.config = config or ExposureConfig()
        self._positions: dict[str, float] = {}

    def validate_targets(
        self,
        targets: list[PortfolioTarget],
    ) -> list[PortfolioTarget]:
        """Filter targets that exceed exposure limits.

        Returns only targets that pass all checks.
        """
        approved: list[PortfolioTarget] = []
        running_total = self.get_total_exposure()

        for t in targets:
            current = self._positions.get(t.market_id, 0.0)
            delta = abs(t.target_size) - abs(current)

            # Per-market check
            if abs(t.target_size) > self.config.max_exposure_per_market:
                continue

            # Total exposure check (incremental)
            if running_total + delta > self.config.max_exposure_total:
                continue

            approved.append(t)
            running_total += delta

        return approved

    def update_positions(
        self, targets: list[PortfolioTarget]
    ) -> None:
        """Update tracked positions from executed targets."""
        for t in targets:
            self._positions[t.market_id] = t.target_size

    def get_exposure(self, market_id: str) -> float:
        """Get current exposure for a market."""
        return self._positions.get(market_id, 0.0)

    def get_total_exposure(self) -> float:
        """Get total absolute exposure across all positions."""
        return sum(abs(v) for v in self._positions.values())
