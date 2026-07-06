"""
Strategy generator — natural language to typed strategy configuration.

Uses keyword matching (Phase 8 MVP) to map NL descriptions to strategy
templates with extracted parameters. Future versions will use LLM-based
intent parsing.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


@dataclass
class ValidationGate:
    """Result of a single validation step in the generation pipeline.

    Gates are ordered and all must pass for the generated config to be
    considered validated.
    """

    name: str
    passed: bool
    message: str


class StrategyTemplate(Enum):
    """Known strategy templates that can be generated."""

    AMM = "amm"
    BANDS = "bands"
    CLASSIC_MM = "classic_mm"
    MOMENTUM = "momentum"
    MAKER_REBATE = "maker_rebate"
    EVENT_MM = "event_mm"
    SNIPER = "sniper"
    COPY_TRADE = "copy_trade"
    FACTOR = "factor"
    CUSTOM = "custom"

    @property
    def required_params(self) -> list[str]:
        return _TEMPLATE_PARAMS[self]["required"]

    @property
    def defaults(self) -> dict[str, Any]:
        return _TEMPLATE_PARAMS[self]["defaults"]


_TEMPLATE_PARAMS: dict[StrategyTemplate, dict[str, Any]] = {
    StrategyTemplate.AMM: {
        "required": ["min_spread", "num_levels"],
        "defaults": {"min_spread": 0.01, "max_spread": 0.05, "num_levels": 5, "tick_size": 0.001},
    },
    StrategyTemplate.BANDS: {
        "required": ["band_spreads"],
        "defaults": {"band_spreads": [0.015, 0.03, 0.05], "exposure_per_band": 20.0},
    },
    StrategyTemplate.CLASSIC_MM: {
        "required": ["spread_pct"],
        "defaults": {"spread_pct": 0.02, "order_size": 10.0, "num_levels": 3},
    },
    StrategyTemplate.MOMENTUM: {
        "required": ["lookback"],
        "defaults": {"lookback": "24h", "top_n": 5, "total_exposure": 500.0},
    },
    StrategyTemplate.FACTOR: {
        "required": ["lookback", "top_n"],
        "defaults": {"lookback": "24h", "top_n": 5, "rebal_freq_hours": 4},
    },
    StrategyTemplate.CUSTOM: {
        "required": [],
        "defaults": {},
    },
}


@dataclass
class GeneratedConfig:
    """Output of the NL → strategy config generation."""

    template: StrategyTemplate
    strategy_name: str
    params: dict[str, Any] = field(default_factory=dict)
    confidence: float = 0.0
    validated: bool = True
    raw_description: str = ""
    validation_results: list[ValidationGate] = field(default_factory=list)
    provenance: str = ""  # Source of the generation (e.g., "keyword", "llm", "manual")
    source_version: str = ""  # Version of the source strategy template
    risk_limits: dict[str, float] = field(default_factory=dict)  # Risk limit overrides
    execution_policy: str = ""  # Execution policy (e.g., "paper", "live", "maker", "taker")

    def to_summary(self) -> str:
        """Return a human-readable summary."""
        return (
            f"Generated '{self.strategy_name}' "
            f"({self.template.name}) "
            f"confidence={self.confidence:.0%}"
        )


class GenerationError(Exception):
    """Raised when strategy generation fails."""


# ── Validation constants ───────────────────────────────────────────────────

_PARAM_TYPES: dict[str, str] = {
    "min_spread": "number",
    "max_spread": "number",
    "spread_pct": "number",
    "tick_size": "number",
    "exposure_per_band": "number",
    "order_size": "number",
    "total_exposure": "number",
    "rebal_freq_hours": "number",
    "num_levels": "int",
    "top_n": "int",
    "lookback": "str",
    "band_spreads": "list",
}

_RISK_LIMITS: dict[str, float] = {
    "max_total_exposure": 100_000.0,
    "max_num_levels": 20,
    "max_top_n": 50,
    "min_spread": 0.0001,
    "max_spread": 0.50,
    "max_position_size": 100_000.0,
    "max_exposure_per_band": 50_000.0,
}


def _check_param_type(value: Any, expected: str) -> bool:
    if expected == "int":
        return isinstance(value, int)
    if expected == "number":
        return isinstance(value, int | float)
    if expected == "str":
        return isinstance(value, str)
    if expected == "list":
        return isinstance(value, list)
    return True


class StrategyGenerator:
    """Maps natural language descriptions to strategy configurations.

    Keyword-based matching for Phase 8 MVP.
    Supports factor discovery descriptions via FactorDiscoveryAgent.
    """

    def __init__(self):
        self._patterns = [
            (re.compile(r"\bamm\b", re.I), self._match_amm),
            (re.compile(r"\bbands?\b", re.I), self._match_bands),
            (re.compile(r"\bclassic\b.*\bmm\b", re.I), self._match_classic_mm),
            (re.compile(r"\bmaker\b.*\brebate\b|\brebate\b", re.I), self._match_maker_rebate),
            (re.compile(r"\bmomentum\b", re.I), self._match_momentum),
            (re.compile(r"\bfactor\b", re.I), self._match_momentum),
            (
                re.compile(r"\b(cross.sectional|volatility|sentiment|fair.value|discover)\b", re.I),
                self._match_factor_discovery,
            ),
        ]

    def _validate(self, config: GeneratedConfig) -> GeneratedConfig:
        """Run all validation gates and update *config* in place.

        Returns the config for chaining.
        """
        gates = [
            self._validate_schema(config),
            self._validate_implementation_status(config),
            self._validate_risk_limits(config),
        ]
        config.validation_results = gates
        config.validated = all(g.passed for g in gates)
        return config

    def _validate_schema(self, config: GeneratedConfig) -> ValidationGate:
        """Gate 1: Check required params exist and types are correct."""
        missing: list[str] = []
        for param in config.template.required_params:
            if param not in config.params:
                missing.append(param)

        type_errors: list[str] = []
        for param, value in config.params.items():
            expected = _PARAM_TYPES.get(param)
            if expected is not None and not _check_param_type(value, expected):
                type_errors.append(f"{param} (got {type(value).__name__}, want {expected})")

        if missing:
            return ValidationGate(
                name="schema",
                passed=False,
                message=f"Missing required params: {', '.join(missing)}",
            )
        if type_errors:
            return ValidationGate(
                name="schema",
                passed=False,
                message=f"Type mismatches: {', '.join(type_errors)}",
            )
        return ValidationGate(
            name="schema",
            passed=True,
            message="All required params present with correct types",
        )

    def _validate_implementation_status(self, config: GeneratedConfig) -> ValidationGate:
        """Gate 2: Check that the strategy template is registered."""
        if config.template in (StrategyTemplate.CUSTOM, StrategyTemplate.FACTOR):
            return ValidationGate(
                name="implementation_status",
                passed=True,
                message=(
                    f"Template '{config.template.value}' is a meta-template "
                    "(no direct plugin required)"
                ),
            )

        from polymind.core.plugin import PluginRegistry

        registry = PluginRegistry()
        registered = registry.get_strategy(config.template.value)
        if registered is not None:
            return ValidationGate(
                name="implementation_status",
                passed=True,
                message=f"Strategy '{config.template.value}' is registered",
            )
        return ValidationGate(
            name="implementation_status",
            passed=False,
            message=(
                f"Strategy '{config.template.value}' is not registered in PluginRegistry. "
                f"Available: {sorted(registry.list_strategies().keys())}"
            ),
        )

    def _validate_risk_limits(self, config: GeneratedConfig) -> ValidationGate:
        """Gate 3: Check params stay within configured risk limits."""
        violations: list[str] = []

        nlevels = config.params.get("num_levels")
        if nlevels is not None and nlevels > _RISK_LIMITS["max_num_levels"]:
            violations.append(
                f"num_levels ({nlevels}) exceeds max ({_RISK_LIMITS['max_num_levels']})"
            )

        top_n = config.params.get("top_n")
        if top_n is not None and top_n > _RISK_LIMITS["max_top_n"]:
            violations.append(f"top_n ({top_n}) exceeds max ({_RISK_LIMITS['max_top_n']})")

        exposure = config.params.get("total_exposure")
        if exposure is not None and exposure > _RISK_LIMITS["max_total_exposure"]:
            violations.append(
                f"total_exposure ({exposure}) exceeds max ({_RISK_LIMITS['max_total_exposure']})"
            )

        epb = config.params.get("exposure_per_band")
        if epb is not None and epb > _RISK_LIMITS["max_exposure_per_band"]:
            violations.append(
                f"exposure_per_band ({epb}) exceeds max ({_RISK_LIMITS['max_exposure_per_band']})"
            )

        min_s = config.params.get("min_spread")
        if min_s is not None and min_s < _RISK_LIMITS["min_spread"]:
            violations.append(f"min_spread ({min_s}) is below min ({_RISK_LIMITS['min_spread']})")

        max_s = config.params.get("max_spread")
        if max_s is not None and max_s > _RISK_LIMITS["max_spread"]:
            violations.append(f"max_spread ({max_s}) exceeds max ({_RISK_LIMITS['max_spread']})")

        if violations:
            return ValidationGate(
                name="risk_limits",
                passed=False,
                message="Risk limit violations: " + "; ".join(violations),
            )
        return ValidationGate(
            name="risk_limits",
            passed=True,
            message="All params within risk limits",
        )

    def _match_factor_discovery(self, description: str) -> GeneratedConfig:
        """Route factor-discovery descriptions to FactorDiscoveryAgent."""
        from polymind.studio.factor_discovery import FactorDiscoveryAgent

        agent = FactorDiscoveryAgent()
        # Run the discover step synchronously within a new event loop
        import asyncio

        try:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            fd = loop.run_until_complete(agent.discover(description))
            loop.close()
        except Exception:
            # Fallback to momentum matching
            return self._match_momentum(description)

        params = dict(fd.params)
        # Use discovery params for strategy config
        top_n = getattr(fd, "top_n", 5)
        params["top_n"] = top_n
        params["lookback"] = getattr(fd, "lookback", "24h")

        return GeneratedConfig(
            template=StrategyTemplate.FACTOR,
            strategy_name=fd.name or "factor_discovery",
            params=params,
            confidence=0.75,
            provenance="keyword",
            source_version="0.7.0",
            execution_policy="paper",
        )

    def generate(self, description: str) -> GeneratedConfig:
        """Parse a NL description and return a validated GeneratedConfig."""
        best_match: GeneratedConfig | None = None
        best_conf = 0.0

        for pattern, matcher in self._patterns:
            if pattern.search(description):
                result = matcher(description)
                if result.confidence > best_conf:
                    best_match = result
                    best_conf = result.confidence

        if best_match is None:
            return self._validate(
                GeneratedConfig(
                    template=StrategyTemplate.CUSTOM,
                    strategy_name="custom_strategy",
                    confidence=0.2,
                    raw_description=description,
                    provenance="keyword",
                    source_version="0.7.0",
                    execution_policy="paper",
                )
            )

        best_match.raw_description = description
        return self._validate(best_match)

    def _match_amm(self, description: str) -> GeneratedConfig:
        params = dict(StrategyTemplate.AMM.defaults)
        name_parts = ["amm"]

        # Extract num_levels
        levels = _extract_int(description, r"(\d+)\s*levels?", 5)
        params["num_levels"] = max(1, levels)
        name_parts.append(f"l{levels}")

        # Extract min_spread
        spread = _extract_pct(description, r"(\d+(?:\.\d+)?)\s*%", 1.0)
        params["min_spread"] = max(0.001, spread / 100.0)
        params["max_spread"] = params["min_spread"] * 5
        name_parts.append(f"s{int(spread)}")

        return GeneratedConfig(
            template=StrategyTemplate.AMM,
            strategy_name="_".join(name_parts),
            params=params,
            confidence=0.9,
            provenance="keyword",
            source_version="0.7.0",
            execution_policy="paper",
        )

    def _match_bands(self, description: str) -> GeneratedConfig:
        params = dict(StrategyTemplate.BANDS.defaults)
        name_parts = ["bands"]

        # Extract percentages
        pcts = re.findall(r"(\d+(?:\.\d+)?)\s*%", description)
        if pcts:
            spreads = [float(p) / 100.0 for p in pcts]
            params["band_spreads"] = spreads
            name_parts.append(f"b{len(spreads)}")

        return GeneratedConfig(
            template=StrategyTemplate.BANDS,
            strategy_name="_".join(name_parts),
            params=params,
            confidence=0.85,
            provenance="keyword",
            source_version="0.7.0",
            execution_policy="paper",
        )

    def _match_maker_rebate(self, description: str) -> GeneratedConfig:
        params = {"pair_strategy": "maker_rebate"}
        return GeneratedConfig(
            template=StrategyTemplate.CUSTOM,
            strategy_name="maker_rebate",
            params=params,
            confidence=0.8,
            provenance="keyword",
            source_version="0.7.0",
            execution_policy="paper",
        )

    def _match_classic_mm(self, description: str) -> GeneratedConfig:
        params = dict(StrategyTemplate.CLASSIC_MM.defaults)
        spread = _extract_pct(description, r"(\d+(?:\.\d+)?)\s*%", 2.0)
        params["spread_pct"] = spread / 100.0
        return GeneratedConfig(
            template=StrategyTemplate.CLASSIC_MM,
            strategy_name="classic_mm",
            params=params,
            confidence=0.85,
            provenance="keyword",
            source_version="0.7.0",
            execution_policy="paper",
        )

    def _match_momentum(self, description: str) -> GeneratedConfig:
        params = dict(StrategyTemplate.MOMENTUM.defaults)
        name_parts = ["momentum"]

        if "7d" in description or "7 day" in description:
            params["lookback"] = "7d"
            name_parts.append("7d")
        elif "4h" in description or "4 hour" in description:
            params["lookback"] = "4h"
            name_parts.append("4h")
        elif "24h" in description or "24 hour" in description:
            params["lookback"] = "24h"
            name_parts.append("24h")

        top_n = _extract_int(description, r"top\s*(\d+)", 5)
        params["top_n"] = top_n

        return GeneratedConfig(
            template=StrategyTemplate.MOMENTUM,
            strategy_name="_".join(name_parts),
            params=params,
            confidence=0.9,
            provenance="keyword",
            source_version="0.7.0",
            execution_policy="paper",
        )


def _extract_int(text: str, pattern: str, default: int) -> int:
    """Extract an integer from text using a regex pattern."""
    m = re.search(pattern, text, re.I)
    if m:
        return int(m.group(1))
    return default


def _extract_pct(text: str, pattern: str, default: float) -> float:
    """Extract a percentage value from text."""
    m = re.search(pattern, text)
    if m:
        return float(m.group(1))
    return default
