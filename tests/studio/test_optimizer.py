"""Tests for strategy parameter optimizer."""

from __future__ import annotations

import pytest

from polymind.studio.optimizer import (
    OptimizationResult,
    OptimizationTarget,
    OptimizerConfig,
    ParamRange,
    StrategyOptimizer,
)


class TestOptimizationTarget:
    def test_members(self):
        assert OptimizationTarget.SHARPE.name == "SHARPE"
        assert OptimizationTarget.SORTINO.name == "SORTINO"
        assert OptimizationTarget.CALMAR.name == "CALMAR"
        assert OptimizationTarget.TOTAL_RETURN.name == "TOTAL_RETURN"
        assert OptimizationTarget.MAX_DRAWDOWN.name == "MAX_DRAWDOWN"

    def test_distinct_values(self):
        values = {m.value for m in OptimizationTarget}
        assert len(values) == 5


class TestParamRange:
    def test_positional_args(self):
        pr = ParamRange("spread", 0.0, 1.0)
        assert pr.name == "spread"
        assert pr.min_val == 0.0
        assert pr.max_val == 1.0
        assert pr.step_size == 1.0
        assert pr.param_type == "float"

    def test_with_step_size(self):
        pr = ParamRange("levels", 1, 10, step_size=1)
        assert pr.step_size == 1

    def test_with_param_type(self):
        pr = ParamRange("count", 1, 100, step_size=1, param_type="int")
        assert pr.param_type == "int"


class TestOptimizationResult:
    def test_defaults(self):
        r = OptimizationResult()
        assert r.params == {}
        assert r.score == 0.0
        assert r.target == OptimizationTarget.SHARPE

    def test_custom_values(self):
        r = OptimizationResult(
            params={"spread": 0.05, "levels": 5},
            score=0.85,
            target=OptimizationTarget.SORTINO,
        )
        assert r.params["spread"] == 0.05
        assert r.score == 0.85
        assert r.target == OptimizationTarget.SORTINO


class TestOptimizerConfig:
    def test_defaults(self):
        cfg = OptimizerConfig()
        assert cfg.target == OptimizationTarget.SHARPE
        assert cfg.max_evals == 100
        assert cfg.random_seed == 42

    def test_custom(self):
        cfg = OptimizerConfig(
            target=OptimizationTarget.CALMAR,
            max_evals=50,
            random_seed=7,
        )
        assert cfg.target == OptimizationTarget.CALMAR
        assert cfg.max_evals == 50
        assert cfg.random_seed == 7


class TestStrategyOptimizer:
    def test_init(self):
        cfg = OptimizerConfig(random_seed=1)
        opt = StrategyOptimizer(cfg)
        assert opt.config is cfg

    def test_random_search_returns_correct_number(self):
        cfg = OptimizerConfig(random_seed=42)
        opt = StrategyOptimizer(cfg)
        param_ranges = [
            ParamRange("spread", 0.01, 0.10, step_size=0.01),
            ParamRange("levels", 1, 10, step_size=1),
        ]
        results = opt._random_search(param_ranges, max_evals=5)
        assert len(results) == 5
        for r in results:
            assert "spread" in r
            assert "levels" in r

    def test_random_search_respects_seed(self):
        cfg = OptimizerConfig(random_seed=99)
        opt = StrategyOptimizer(cfg)
        param_ranges = [ParamRange("x", 0.0, 1.0, step_size=0.1)]
        r1 = opt._random_search(param_ranges, max_evals=3)
        r2 = opt._random_search(param_ranges, max_evals=3)
        assert r1 == r2

    def test_random_search_int_type(self):
        cfg = OptimizerConfig(random_seed=42)
        opt = StrategyOptimizer(cfg)
        param_ranges = [ParamRange("n", 1, 10, step_size=1, param_type="int")]
        results = opt._random_search(param_ranges, max_evals=10)
        for r in results:
            assert isinstance(r["n"], int)

    @pytest.mark.asyncio
    async def test_optimize_runs_without_error(self):
        cfg = OptimizerConfig(max_evals=3, random_seed=0)
        opt = StrategyOptimizer(cfg)
        param_ranges = [
            ParamRange("spread", 0.01, 0.05, step_size=0.01),
        ]
        results = await opt.optimize(
            strategy_cls=None,  # type: ignore[arg-type]
            param_ranges=param_ranges,
            data=None,
        )
        assert len(results) == 3
        for r in results:
            assert isinstance(r, OptimizationResult)
            assert "spread" in r.params
            assert r.score == 0.0
            assert r.target == OptimizationTarget.SHARPE
