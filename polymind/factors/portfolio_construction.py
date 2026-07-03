"""
Portfolio construction for the factor pipeline.

Converts ranked scores into PortfolioTargets under risk constraints.
Supports decile-based selection, sizing based on rank, and basic
exposure limits.
"""

from __future__ import annotations

from dataclasses import dataclass

from polymind.core.portfolio import PortfolioTarget, PositionDirection


@dataclass
class PortfolioConfig:
    """Configuration for portfolio construction."""

    top_n: int = 5  # number of top-ranked markets to take
    max_exposure_per_market: float = 100.0  # max size per market
    total_exposure: float = 500.0  # max total exposure (sum of all positions)
    min_confidence: float = 0.1  # minimum confidence to take a position
    direction_long_above: float = 0.0  # positive scores → LONG, negative → SHORT


def select_top_n(
    scores: dict[str, float],
    n: int,
) -> list[str]:
    """Select the top N markets by score.

    Args:
        scores: Dict of market_id → score.
        n: Maximum number of markets to select.

    Returns:
        List of market_ids ordered by descending score.
    """
    sorted_markets = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    return [mid for mid, _ in sorted_markets[:n]]


def select_top_and_bottom_n(
    scores: dict[str, float],
    n: int,
) -> dict[str, PositionDirection]:
    """Select top N (LONG) and bottom N (SHORT) markets.

    Args:
        scores: Dict of market_id → score.
        n: Number of markets to select from each end.

    Returns:
        Dict of market_id → direction.
    """
    sorted_items = sorted(scores.items(), key=lambda x: x[1], reverse=True)
    result: dict[str, PositionDirection] = {}

    for mid, _ in sorted_items[:n]:
        result[mid] = PositionDirection.LONG

    for mid, _ in sorted_items[-n:]:
        if mid not in result:
            result[mid] = PositionDirection.SHORT

    return result


def size_by_rank(
    scores: dict[str, float],
    config: PortfolioConfig,
) -> dict[str, float]:
    """Assign sizes proportional to rank score.

    Higher score → larger size, clamped by max_exposure_per_market
    and total_exposure.  Every market gets at least a minimum size.
    """
    if not scores:
        return {}

    min_score = min(scores.values())
    max_score = max(scores.values())
    score_range = max_score - min_score

    if score_range == 0:
        equal_size = min(
            config.max_exposure_per_market,
            config.total_exposure / len(scores),
        )
        return dict.fromkeys(scores, equal_size)

    raw: dict[str, float] = {}
    for mid, score in scores.items():
        normalized = (score - min_score) / score_range  # 0.0–1.0
        # Ensure every market gets at least 10% of max
        adjusted = 0.1 + 0.9 * normalized
        size = adjusted * config.max_exposure_per_market
        raw[mid] = size

    # Scale down if total exceeds limit
    total_raw = sum(raw.values())
    if total_raw > config.total_exposure:
        scale = config.total_exposure / total_raw
        raw = {mid: s * scale for mid, s in raw.items()}

    return raw


def construct_portfolio(
    scores: dict[str, float],
    config: PortfolioConfig,
) -> list[PortfolioTarget]:
    """Convert ranked scores into a list of PortfolioTargets.

    Selects top N markets (by absolute score), assigns LONG/SHORT
    based on sign, sizes proportionally to score magnitude.

    Args:
        scores: Dict of market_id → score.
        config: Portfolio construction configuration.

    Returns:
        List of PortfolioTargets.
    """
    if not scores:
        return []

    # Filter by min_confidence (absolute score)
    filtered = {mid: sc for mid, sc in scores.items() if abs(sc) >= config.min_confidence}
    if not filtered:
        return []

    # Select top N by absolute score
    abs_sorted = sorted(filtered.items(), key=lambda x: abs(x[1]), reverse=True)
    selected = dict(abs_sorted[: config.top_n])

    # Compute sizes
    sizes = size_by_rank(selected, config)

    targets: list[PortfolioTarget] = []
    for i, (mid, score) in enumerate(
        sorted(selected.items(), key=lambda x: abs(x[1]), reverse=True)
    ):
        direction = (
            PositionDirection.LONG
            if score >= config.direction_long_above
            else PositionDirection.SHORT
        )
        size = sizes.get(mid, 0.0)
        if size <= 0:
            continue

        targets.append(
            PortfolioTarget(
                market_id=mid,
                direction=direction,
                target_size=size,
                confidence=abs(score),
                rank=i + 1,
                reason=f"rank {i + 1}/{config.top_n} score={score:.4f}",
            )
        )

    return targets
