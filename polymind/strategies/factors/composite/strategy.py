"""
Composite factor strategy — weighted combination of multiple signals.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from polymind.factors.pipeline import UniverseSnapshot
from polymind.factors.registry import FactorMetadata, FactorSignalModel


@dataclass
class CompositeConfig:
    """Configuration for composite factor."""

    weights: dict[str, float] = field(default_factory=lambda: {
        "momentum": 0.4,
        "volatility": 0.2,
        "sentiment": 0.2,
        "fair_value": 0.2,
    })
    normalize: bool = True


class CompositeFactor(FactorSignalModel):
    """Composite factor that blends multiple sub-signals.

    Weighted combination of registered sub-factors. Sub-factors
    must be pre-registered and passed at construction time.
    """

    def __init__(
        self,
        sub_factors: dict[str, FactorSignalModel],
        config: CompositeConfig | None = None,
    ):
        self.config = config or CompositeConfig()
        self.sub_factors = sub_factors
        metadata = FactorMetadata(
            name="composite",
            version="1.0.0",
            description="Composite factor blending multiple signals",
            tags=["composite", "multi-factor"],
        )
        super().__init__(metadata)

    async def compute_scores(self, universe: UniverseSnapshot) -> dict[str, float]:
        """Compute weighted composite scores."""
        all_scores: dict[str, dict[str, float]] = {}

        for name, factor in self.sub_factors.items():
            weight = self.config.weights.get(name, 0.0)
            if weight == 0:
                continue
            scores = await factor.compute_scores(universe)
            if self.config.normalize:
                scores = self._normalize(scores)
            for mid, score in scores.items():
                if mid not in all_scores:
                    all_scores[mid] = {}
                all_scores[mid][name] = score * weight

        # Sum weighted scores per market
        composite: dict[str, float] = {}
        for mid, subs in all_scores.items():
            composite[mid] = sum(subs.values())

        return composite

    @staticmethod
    def _normalize(scores: dict[str, float]) -> dict[str, float]:
        """Min-max normalize scores to 0-1 range."""
        if not scores:
            return {}
        values = list(scores.values())
        min_v, max_v = min(values), max(values)
        diff = max_v - min_v
        if diff == 0:
            return dict.fromkeys(scores, 0.5)
        return {k: (v - min_v) / diff for k, v in scores.items()}
