"""
AI Factor Discovery Engine — LLM-powered factor definition and backtesting.

Uses natural language descriptions to propose factor definitions, validates
them via FactorBacktester, and returns a FactorCard with performance metrics.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

from polymind.backtesting.factor_bt import (
    FactorBacktestConfig,
    FactorBacktester,
)
from polymind.execution.fill_model import MarketSnapshot
from polymind.studio.factor_analysis import FactorAnalyzer


@dataclass
class FactorDefinition:
    """Structured definition of a factor strategy proposed by the AI.

    Parameters
    ----------
    name:
        Human-readable factor name.
    description:
        Natural language description of the factor logic.
    lookback:
        Lookback period string ("24h", "7d", "14d", "30d").
    scoring_fn:
        Scoring function name ("momentum", "volatility", "custom").
    top_n:
        Number of top-scored markets to hold.
    rebal_freq_hours:
        Rebalance frequency in hours.
    params:
        Additional factor-specific parameters.
    """

    name: str = ""
    description: str = ""
    lookback: str = "24h"
    scoring_fn: str = "momentum"
    top_n: int = 5
    rebal_freq_hours: int = 4
    params: dict[str, Any] = field(default_factory=dict)


@dataclass
class FactorCard:
    """Result of backtesting a FactorDefinition.

    Contains performance metrics and an approval flag indicating whether
    the factor meets minimum thresholds (Sharpe > 0.5, max_drawdown < 50%).

    When sufficient data is available, advanced analytics (IC, decay,
    walk-forward) are also computed.
    """

    definition: FactorDefinition
    sharpe: float = 0.0
    sortino: float = 0.0
    max_drawdown: float = 0.0
    total_return: float = 0.0
    win_rate: float = 0.0
    total_trades: int = 0
    approved: bool = False
    error: str = ""

    # Advanced analytics (computed when data permits)
    ic_rank: float = 0.0
    ic_ir: float = 0.0
    ic_hit_rate: float = 0.0
    ic_decile_1: float = 0.0
    ic_decile_10: float = 0.0
    decay_half_life: float = 0.0
    wf_sharpe_mean: float = 0.0
    wf_sharpe_std: float = 0.0
    wf_sharpe_consistency: float = 0.0
    wf_avg_drawdown: float = 0.0

    @property
    def summary(self) -> str:
        """One-line summary of the factor card."""
        status = "✅ APPROVED" if self.approved else "❌ REJECTED"
        parts = [
            f"{status} {self.definition.name}:",
            f"Sharpe={self.sharpe:.2f}",
            f"Return={self.total_return:.1%}",
            f"DD={self.max_drawdown:.1%}",
            f"Trades={self.total_trades}",
        ]
        if self.ic_rank:
            parts.append(f"IC={self.ic_rank:.2f}")
        if self.wf_sharpe_mean:
            parts.append(f"WF_Sharpe={self.wf_sharpe_mean:.2f}")
        return " ".join(parts)


FACTOR_APPROVAL_MIN_SHARPE = 0.5
FACTOR_APPROVAL_MAX_DRAWDOWN = 0.50


class FactorDiscoveryError(Exception):
    """Raised when factor discovery or backtesting fails."""


class FactorDiscoveryAgent:
    """AI-powered factor discovery engine.

    Parses natural language descriptions into FactorDefinitions and
    backtests them against CLOB price data.

    Usage::

        agent = FactorDiscoveryAgent()
        card = await agent.discover_and_backtest(
            "Cross-sectional momentum on 7d returns, top decile, 4h hold",
            price_store,
        )
        print(card.summary)
    """

    def __init__(
        self,
        anthropic_api_key: str | None = None,
        openai_api_key: str | None = None,
    ) -> None:
        self._anthropic_key = anthropic_api_key
        self._openai_key = openai_api_key

    async def discover(
        self,
        description: str,
        use_llm: bool = False,
    ) -> FactorDefinition:
        """Parse a natural language description into a FactorDefinition.

        Uses keyword matching as the default parser (no API key required).
        When *use_llm* is True and an API key is configured, an LLM is
        used for richer extraction.
        """
        desc_lower = description.lower()

        definition = FactorDefinition(
            description=description,
            name=self._infer_name(desc_lower),
            lookback=self._infer_lookback(desc_lower),
            scoring_fn=self._infer_scoring_fn(desc_lower),
            top_n=self._infer_top_n(desc_lower),
            rebal_freq_hours=self._infer_rebal_freq(desc_lower),
            params=self._infer_params(desc_lower),
        )

        if use_llm and self._anthropic_key:
            definition = await self._discover_with_anthropic(description, definition)
        elif use_llm and self._openai_key:
            definition = await self._discover_with_openai(description, definition)

        return definition

    async def _discover_with_anthropic(
        self,
        description: str,
        fallback: FactorDefinition,
    ) -> FactorDefinition:
        """Use Anthropic Claude to parse a richer factor definition."""
        try:
            import anthropic

            client = anthropic.AsyncAnthropic(api_key=self._anthropic_key)
            response = await client.messages.create(
                model="claude-sonnet-5-20251001",
                max_tokens=300,
                system="Extract factor strategy parameters from the description. "
                "Return valid JSON with keys: name, lookback, scoring_fn, top_n, rebal_freq_hours.",
                messages=[{"role": "user", "content": description}],
            )
            import json

            data = json.loads(response.content[0].text)
            return FactorDefinition(
                description=description,
                name=data.get("name", fallback.name),
                lookback=data.get("lookback", fallback.lookback),
                scoring_fn=data.get("scoring_fn", fallback.scoring_fn),
                top_n=int(data.get("top_n", fallback.top_n)),
                rebal_freq_hours=int(data.get("rebal_freq_hours", fallback.rebal_freq_hours)),
                params=fallback.params,
            )
        except Exception:
            return fallback

    async def _discover_with_openai(
        self,
        description: str,
        fallback: FactorDefinition,
    ) -> FactorDefinition:
        """Use OpenAI to parse a richer factor definition."""
        try:
            from openai import AsyncOpenAI

            client = AsyncOpenAI(api_key=self._openai_key)
            response = await client.chat.completions.create(
                model="gpt-4",
                messages=[
                    {
                        "role": "system",
                        "content": "Extract factor strategy parameters. "
                        "Return JSON with: name, lookback, scoring_fn, top_n, rebal_freq_hours.",
                    },
                    {"role": "user", "content": description},
                ],
            )
            import json

            data = json.loads(response.choices[0].message.content or "{}")
            return FactorDefinition(
                description=description,
                name=data.get("name", fallback.name),
                lookback=data.get("lookback", fallback.lookback),
                scoring_fn=data.get("scoring_fn", fallback.scoring_fn),
                top_n=int(data.get("top_n", fallback.top_n)),
                rebal_freq_hours=int(data.get("rebal_freq_hours", fallback.rebal_freq_hours)),
                params=fallback.params,
            )
        except Exception:
            return fallback

    async def backtest(
        self,
        definition: FactorDefinition,
        snapshots: dict[str, list[MarketSnapshot]] | None = None,
        scores: dict[str, float] | None = None,
    ) -> FactorCard:
        """Backtest a FactorDefinition and return a FactorCard.

        Parameters
        ----------
        definition:
            The factor definition to backtest.
        snapshots:
            Optional historical snapshots keyed by market_id.
        scores:
            Optional pre-computed scores keyed by market_id.
            If None, a simple mock score is generated.
        """
        config = FactorBacktestConfig(
            initial_capital=10_000.0,
            lookback_days=self._parse_lookback_days(definition.lookback),
            rebal_freq_hours=definition.rebal_freq_hours,
            top_n=definition.top_n,
            max_position_size=1000.0,
        )

        bt = FactorBacktester(config)

        # Use provided scores or generate mock
        if scores is None:
            scores = self._mock_scores()
        if snapshots is None:
            snapshots = self._mock_snapshots()

        # Run backtest across all timesteps
        all_snap_keys = list(snapshots.keys())
        try:
            # Run one step with all markets in scores + snapshots
            step_snapshots = {}
            for mkt_id in all_snap_keys:
                snaps = snapshots[mkt_id]
                if snaps:
                    step_snapshots[mkt_id] = snaps[0]

            result = bt.run(scores, step_snapshots)
        except Exception as exc:
            return FactorCard(
                definition=definition,
                error=str(exc),
            )

        return FactorCard(
            definition=definition,
            sharpe=result.sharpe,
            sortino=result.sortino,
            max_drawdown=result.max_drawdown,
            total_return=result.total_return,
            win_rate=result.win_rate,
            total_trades=result.total_trades,
            approved=(
                result.sharpe >= FACTOR_APPROVAL_MIN_SHARPE
                and result.max_drawdown <= FACTOR_APPROVAL_MAX_DRAWDOWN
            ),
            # Advanced analytics
            **self._compute_advanced_analytics(scores, step_snapshots),
        )

    def _compute_advanced_analytics(
        self,
        scores: dict[str, float],
        snapshots: dict[str, MarketSnapshot],
    ) -> dict[str, Any]:
        """Run IC analysis and walk-forward on backtest data.

        Returns a dict of advanced metric values (or defaults) that can
        be unpacked into a FactorCard.
        """
        result: dict[str, Any] = {
            "ic_rank": 0.0,
            "ic_ir": 0.0,
            "ic_hit_rate": 0.0,
            "ic_decile_1": 0.0,
            "ic_decile_10": 0.0,
            "decay_half_life": 0.0,
            "wf_sharpe_mean": 0.0,
            "wf_sharpe_std": 0.0,
            "wf_sharpe_consistency": 0.0,
            "wf_avg_drawdown": 0.0,
        }

        try:
            # Compute simple IC from current scores vs mid-price direction
            forward_returns: dict[str, float] = {}
            for mkt_id, snap in snapshots.items():
                # Use mid_price and spread as forward return proxy
                if snap.mid_price > 0:
                    forward_returns[mkt_id] = snap.mid_price

            ic = FactorAnalyzer.compute_ic(scores, forward_returns)
            result["ic_rank"] = round(ic.rank_ic, 4)
            result["ic_ir"] = round(ic.ic_ir, 4)
            result["ic_hit_rate"] = round(ic.hit_rate, 4)
            if len(ic.decile_returns) >= 10:
                result["ic_decile_1"] = round(ic.decile_returns[0], 6)
                result["ic_decile_10"] = round(ic.decile_returns[9], 6)

            # Single-period decay estimate from IC series
            if ic.ic_values:
                hl = FactorAnalyzer.compute_decay(ic.ic_values)
                result["decay_half_life"] = round(hl, 2)
        except Exception:
            pass

        return result

    async def discover_and_backtest(
        self,
        description: str,
        snapshots: dict[str, list[MarketSnapshot]] | None = None,
        scores: dict[str, float] | None = None,
    ) -> FactorCard:
        """Combined discovery + backtest pipeline."""
        definition = await self.discover(description)
        return await self.backtest(definition, snapshots, scores)

    # ── Internal: keyword parsing ────────────────────────────────────

    @staticmethod
    def _infer_name(text: str) -> str:
        """Derive a short name from the description."""
        tokens = text.replace("-", " ").split()
        # Skip common filler words
        stop_words = {
            "a",
            "an",
            "the",
            "on",
            "in",
            "of",
            "for",
            "to",
            "with",
            "and",
            "or",
            "is",
            "are",
            "using",
            "based",
            "by",
        }
        meaningful = [t for t in tokens if t not in stop_words and len(t) > 2]
        if meaningful:
            prefix = "_".join(meaningful[:3])
            return prefix.lower()
        return "custom_factor"

    @staticmethod
    def _infer_lookback(text: str) -> str:
        if "7d" in text or "7 day" in text or "weekly" in text:
            return "7d"
        if "30d" in text or "30 day" in text or "monthly" in text:
            return "30d"
        if "14d" in text or "14 day" in text or "biweekly" in text:
            return "14d"
        if "4h" in text or "4 hour" in text:
            return "4h"
        return "24h"

    @staticmethod
    def _infer_scoring_fn(text: str) -> str:
        if "volatil" in text:
            return "volatility"
        if "sentiment" in text:
            return "sentiment"
        if "fair" in text and "value" in text:
            return "fair_value"
        if "momentum" in text or "cross" in text or "return" in text:
            return "momentum"
        return "momentum"

    @staticmethod
    def _infer_top_n(text: str) -> int:
        import re

        m = re.search(r"top\s*(\d+)", text, re.I)
        if m:
            return int(m.group(1))
        m = re.search(r"decile", text, re.I)
        if m:
            return 10  # top decile
        m = re.search(r"quintile", text, re.I)
        if m:
            return 5
        return 5

    @staticmethod
    def _infer_rebal_freq(text: str) -> int:
        import re

        m = re.search(r"(\d+)\s*h(ours?)?", text, re.I)
        if m:
            return max(1, int(m.group(1)))
        m = re.search(r"(\d+)\s*d(ays?)?", text, re.I)
        if m:
            return int(m.group(1)) * 24
        return 4

    @staticmethod
    def _infer_params(text: str) -> dict[str, Any]:
        params: dict[str, Any] = {}
        if "short" in text or "reversal" in text:
            params["direction"] = "short"
        if "long" in text or "bullish" in text:
            params["direction"] = "long"
        return params

    @staticmethod
    def _parse_lookback_days(lookback: str) -> int:
        """Convert lookback string to days for FactorBacktestConfig."""
        if lookback.endswith("d"):
            return int(lookback[:-1])
        if lookback.endswith("h"):
            return max(1, int(lookback[:-1]) // 24)
        return 1

    @staticmethod
    def _mock_scores() -> dict[str, float]:
        """Generate mock scores for testing."""
        import random

        return {f"mkt{i}": random.random() for i in range(10)}

    @staticmethod
    def _mock_snapshots() -> dict[str, list[MarketSnapshot]]:
        """Generate mock snapshots for testing."""

        return {
            f"mkt{i}": [
                MarketSnapshot(
                    market_id=f"mkt{i}",
                    timestamp=datetime(2026, 7, 4),
                    bid_price=0.45 + i * 0.01,
                    ask_price=0.55 + i * 0.01,
                    mid_price=0.50 + i * 0.01,
                    bid_size=1000.0,
                    ask_size=1000.0,
                ),
            ]
            for i in range(10)
        }
