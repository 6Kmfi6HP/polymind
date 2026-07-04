"""
Template Library — registry of all pre-configured strategy templates.

Each template bundles a strategy type with sensible defaults, risk limits,
and documentation for one-command deployment.
"""

from __future__ import annotations

from polymind.templates.base import TemplateInfo


class TemplateLibrary:
    """Registry of deployable strategy templates.

    Usage::

        lib = TemplateLibrary()
        for t in lib.list_templates():
            print(t.name, t.description)
        info = lib.get_template("amm_concentrated")
        config = lib.instantiate("amm_concentrated", overrides={"budget": 500})
    """

    def __init__(self) -> None:
        self._templates: dict[str, TemplateInfo] = {}
        self._register_all()

    # ── Public API ────────────────────────────────────────────────────

    def list_templates(self) -> list[TemplateInfo]:
        """Return all registered templates."""
        return list(self._templates.values())

    def get_template(self, name: str) -> TemplateInfo | None:
        """Look up a template by name."""
        return self._templates.get(name)

    def instantiate(
        self,
        name: str,
        overrides: dict | None = None,
    ) -> TemplateInfo | None:
        """Return a copy of the template with optional param overrides."""
        info = self.get_template(name)
        if info is None:
            return None
        merged_params = dict(info.params)
        if overrides:
            merged_params.update(overrides)
        return TemplateInfo(
            name=info.name,
            description=info.description,
            strategy_type=info.strategy_type,
            params=merged_params,
            risk_limits=dict(info.risk_limits),
            tags=list(info.tags),
        )

    NAMES: list[str] = [
        "amm_concentrated",
        "bands_multi",
        "classic_mm_simple",
        "maker_rebate_pair",
        "event_mm_trigger",
        "sniper_discount",
        "momentum_factor",
    ]

    # ── Internal: register all templates ──────────────────────────────

    def _register_all(self) -> None:
        for method_name in dir(self):
            if method_name.startswith("_build_"):
                info = getattr(self, method_name)()
                self._templates[info.name] = info

    @staticmethod
    def _build_amm_concentrated() -> TemplateInfo:
        return TemplateInfo(
            name="amm_concentrated",
            description="AMM concentrated-liquidity market making. "
            "Places multiple bid/ask levels around the mid price. "
            "Best for active markets with tight spreads.",
            strategy_type="amm",
            params={
                "min_spread": 0.01,
                "max_spread": 0.05,
                "num_levels": 5,
                "tick_size": 0.001,
                "budget": 200.0,
                "depth": 0.1,
            },
            risk_limits={"max_position_size": 50.0, "max_exposure": 500.0},
            tags=["market-making", "amm", "concentrated", "beginner"],
        )

    @staticmethod
    def _build_bands_multi() -> TemplateInfo:
        return TemplateInfo(
            name="bands_multi",
            description="Bands price-margin market making with multiple "
            "exposure bands. Places orders at increasing distances from "
            "the mid price with graduated position sizes.",
            strategy_type="bands",
            params={
                "band_spreads": [0.015, 0.03, 0.05],
                "exposure_per_band": 20.0,
                "num_bands": 3,
                "tick_size": 0.001,
            },
            risk_limits={"max_position_size": 60.0, "max_exposure": 600.0},
            tags=["market-making", "bands", "multi-level", "intermediate"],
        )

    @staticmethod
    def _build_classic_mm_simple() -> TemplateInfo:
        return TemplateInfo(
            name="classic_mm_simple",
            description="Simple sell-only market making. Places limit "
            "sell orders above the bid price. Ideal for earning maker "
            "rebates on stable markets.",
            strategy_type="classic_mm",
            params={
                "spread_pct": 0.02,
                "order_size": 10.0,
                "num_levels": 3,
            },
            risk_limits={"max_position_size": 30.0, "max_exposure": 300.0},
            tags=["market-making", "simple", "sell-only", "beginner"],
        )

    @staticmethod
    def _build_maker_rebate_pair() -> TemplateInfo:
        return TemplateInfo(
            name="maker_rebate_pair",
            description="Maker rebate arbitrage on YES/NO pairs. "
            "Places paired orders on both sides to capture the "
            "YES+NO < 1 spread and earn maker rebates.",
            strategy_type="maker_rebate",
            params={
                "max_spread": 0.03,
                "order_size": 10.0,
                "merge_on_fill": True,
                "rebate_threshold": 0.005,
            },
            risk_limits={"max_position_size": 20.0, "max_exposure": 200.0},
            tags=["market-making", "maker-rebate", "pair", "arbitrage"],
        )

    @staticmethod
    def _build_event_mm_trigger() -> TemplateInfo:
        return TemplateInfo(
            name="event_mm_trigger",
            description="Event-driven market making. Widens spreads "
            "during high-volatility events and tightens during normal "
            "conditions. Best for news-driven markets.",
            strategy_type="event_mm",
            params={
                "spread_pct": 0.05,
                "order_size": 10.0,
                "cooldown_seconds": 300,
            },
            risk_limits={"max_position_size": 40.0, "max_exposure": 400.0},
            tags=["market-making", "event-driven", "volatility"],
        )

    @staticmethod
    def _build_sniper_discount() -> TemplateInfo:
        return TemplateInfo(
            name="sniper_discount",
            description="Deep-discount GTC limit order sniper. Watches "
            "for prices far below fair value and places buy orders to "
            "capture the rebound. Uses mid-price as fair value estimate.",
            strategy_type="sniper",
            params={
                "discount_threshold": 0.50,
                "order_size": 20.0,
                "fair_value_source": "mid",
                "max_position": 200.0,
            },
            risk_limits={"max_position_size": 100.0, "max_exposure": 200.0},
            tags=["sniper", "discount", "reversal", "advanced"],
        )

    @staticmethod
    def _build_momentum_factor() -> TemplateInfo:
        return TemplateInfo(
            name="momentum_factor",
            description="Cross-sectional momentum factor strategy. "
            "Scores markets by recent returns and holds the top-ranked "
            "positions. 24h lookback, rebalance every 4 hours.",
            strategy_type="momentum",
            params={
                "lookback": "24h",
                "top_n": 5,
                "rebal_freq_hours": 4,
                "total_exposure": 500.0,
            },
            risk_limits={
                "max_position_size": 100.0,
                "max_exposure": 500.0,
                "max_daily_loss": 50.0,
            },
            tags=["factor", "momentum", "cross-sectional", "advanced"],
        )
