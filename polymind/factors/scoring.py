"""
Scoring functions for the factor pipeline.

Score markets based on their features. Higher score = more attractive.
"""

from __future__ import annotations

from typing import Dict

from polymind.factors.pipeline import MarketFeatures, UniverseSnapshot


def momentum_score(
    universe: UniverseSnapshot,
    lookback: str = "24h",
) -> Dict[str, float]:
    """Score markets by momentum signal.

    Args:
        universe: The filtered universe snapshot.
        lookback: Which momentum lookback to use ('4h', '24h', '7d').

    Returns:
        Dict of market_id → score (-1 to 1 range, positive = momentum).
    """
    scores: Dict[str, float] = {}
    for mid, mf in universe.markets.items():
        if lookback == "4h":
            mom = mf.momentum_4h
        elif lookback == "24h":
            mom = mf.momentum_24h
        elif lookback == "7d":
            mom = mf.momentum_7d
        else:
            mom = None

        if mom is not None:
            scores[mid] = mom
    return scores


def rank_normalize(scores: Dict[str, float]) -> Dict[str, float]:
    """Convert raw scores to percentile ranks (0.0–1.0)."""
    if not scores:
        return {}

    sorted_items = sorted(scores.items(), key=lambda x: x[1])
    n = len(sorted_items)
    return {
        mid: rank / (n - 1) if n > 1 else 1.0
        for rank, (mid, _) in enumerate(sorted_items)
    }
