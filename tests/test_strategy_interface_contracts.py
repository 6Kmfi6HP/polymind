"""Strategy interface contracts."""

import importlib
import inspect
from typing import get_args, get_type_hints

import pytest


def test_strategy_module_exposes_order_intent_and_factor_base():
    strategy = importlib.import_module("polymind.core.strategy")

    missing = {"OrderIntent", "BaseFactorStrategy"} - set(dir(strategy))

    assert not missing, f"polymind.core.strategy is missing public strategy contracts: {missing}"
    assert issubclass(strategy.BaseFactorStrategy, strategy.BaseMMStrategy)
    assert strategy.BaseFactorStrategy is not strategy.BaseMMStrategy


def test_order_intent_carries_executable_order_fields():
    strategy = importlib.import_module("polymind.core.strategy")
    OrderIntent = getattr(strategy, "OrderIntent")

    intent = OrderIntent(market_id="market-1", outcome="YES", side="buy", price=0.42, size=15)

    assert intent.market_id == "market-1"
    assert intent.outcome == "YES"
    assert intent.side == "buy"
    assert intent.price == 0.42
    assert intent.size == 15


def test_base_market_making_strategy_retains_place_orders_returning_order_intents():
    strategy = importlib.import_module("polymind.core.strategy")
    BaseMMStrategy = strategy.BaseMMStrategy
    OrderIntent = getattr(strategy, "OrderIntent")

    assert "place_orders" in BaseMMStrategy.__dict__
    assert inspect.iscoroutinefunction(BaseMMStrategy.place_orders)

    return_annotation = get_type_hints(BaseMMStrategy.place_orders, vars(strategy)).get("return")

    assert OrderIntent in get_args(return_annotation), (
        "BaseMMStrategy.place_orders must declare a collection of OrderIntent objects, "
        "not transport-owned exchange order results"
    )


def test_factor_strategy_base_builds_order_intents_without_owning_transport():
    strategy = importlib.import_module("polymind.core.strategy")
    BaseFactorStrategy = getattr(strategy, "BaseFactorStrategy")
    OrderIntent = getattr(strategy, "OrderIntent")

    assert "place_orders" in BaseFactorStrategy.__dict__, (
        "BaseFactorStrategy should provide the factor-to-OrderIntent bridge for factor strategies"
    )
    assert not getattr(BaseFactorStrategy.place_orders, "__isabstractmethod__", False)

    return_annotation = get_type_hints(BaseFactorStrategy.place_orders, vars(strategy)).get("return")

    assert OrderIntent in get_args(return_annotation)
