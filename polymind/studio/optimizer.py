"""Strategy parameter optimizer."""

from __future__ import annotations

import random
from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Any


class OptimizationTarget(Enum):
    SHARPE = auto()
    SORTINO = auto()
    CALMAR = auto()
    TOTAL_RETURN = auto()
    MAX_DRAWDOWN = auto()


@dataclass
class ParamRange:
    name: str
    min_val: float
    max_val: float
    step_size: float = 1.0
    param_type: str = "float"


@dataclass
class OptimizationResult:
    params: dict[str, Any] = field(default_factory=dict)
    score: float = 0.0
    target: OptimizationTarget = OptimizationTarget.SHARPE


@dataclass
class OptimizerConfig:
    target: OptimizationTarget = OptimizationTarget.SHARPE
    max_evals: int = 100
    random_seed: int = 42


class StrategyOptimizer:
    def __init__(self, config: OptimizerConfig) -> None:
        self.config = config

    def _random_search(
        self, param_ranges: list[ParamRange], max_evals: int
    ) -> list[dict[str, Any]]:
        random.seed(self.config.random_seed)
        results: list[dict[str, Any]] = []
        for _ in range(max_evals):
            params: dict[str, Any] = {}
            for pr in param_ranges:
                val = random.uniform(pr.min_val, pr.max_val)
                if pr.step_size > 0:
                    val = round(val / pr.step_size) * pr.step_size
                if pr.param_type == "int":
                    val = int(val)
                params[pr.name] = val
            results.append(params)
        return results

    async def optimize(
        self,
        strategy_cls: type,
        param_ranges: list[ParamRange],
        data: Any,
    ) -> list[OptimizationResult]:
        samples = self._random_search(param_ranges, self.config.max_evals)
        results: list[OptimizationResult] = []
        for params in samples:
            results.append(
                OptimizationResult(
                    params=params,
                    score=0.0,
                    target=self.config.target,
                )
            )
        return results
