# Strategies API

The `polymind.strategies` package provides the strategy registry and all
market-making policy implementations. Strategies are pure policies with no
CLOB transport side effects.

## Module Overview

```
polymind.strategies
├── __init__.py          — Strategy registry (register, get_strategy, list_strategies)
├── market_making/       — Bid/ask policy engines
│   ├── amm/             — Concentrated-liquidity ladder math
│   ├── bands/           — Price-margin band sizing math
│   └── classic_mm/      — Split/limit-sell policy surface
└── factors/             — Strategy adapters around factor engine components
    ├── momentum/
    ├── regime/
    ├── sentiment/
    ├── fair_value/
    ├── structural/
    └── composite/
```

## Strategy Registry

`polymind.strategies.__init__`

A simple registry that discovers and manages all available strategies.

```python
def register(name: str) -> Callable:
    """Decorator to register a strategy class."""

def get_strategy(name: str, config: Any = None) -> BaseMMStrategy:
    """Instantiate a registered strategy by name."""

def list_strategies() -> dict[str, str]:
    """List all registered strategies with descriptions."""
```

**Usage:**

```python
from polymind.strategies import register, get_strategy, list_strategies

@register("my_strategy")
class MyStrategy(BaseMMStrategy):
    """My custom strategy."""
    ...

# Instantiate
strat = get_strategy("my_strategy", config)

# List all
for name, desc in list_strategies().items():
    print(f"{name}: {desc}")
```

## Market-Making Strategies

### AMM (Concentrated Liquidity)

Port of the official Polymarket market maker keeper. Uses concentrated-liquidity
ladder math to place orders across a price range.

- **Source:** `polymarket/poly-market-maker`
- **Key invariants:** Ladder symmetry, no band overlap, graceful cancel/replace
- **Output:** Multiple `OrderIntent` objects at ladder rungs

### Bands (Price-Margin Band Sizing)

Port of the official Polymarket Bands strategy. Sizes orders based on price-margin
bands with configurable width and spacing.

- **Source:** `polymarket/poly-market-maker`
- **Key invariants:** Band overlap checks, band fill order, cancel/replace semantics
- **Output:** `OrderIntent` objects at band edges

### Classic MM

Split/limit-sell policy for standard market-making. Places bid/ask spreads
around a target price.

- **Source:** Reference workflow patterns
- **Output:** BUY/SELL `OrderIntent` pairs

## Factor Strategies

Factor strategies do **not** inherit from `BaseMMStrategy**. They share a neutral
strategy contract and use an execution bridge when a directional factor needs
market-making-style passive execution.

| Strategy | Description |
|----------|-------------|
| **Momentum** | Cross-sectional momentum with configurable lookbacks (4h, 24h, 7d, 21d) |
| **Regime** | Volatility and regime detection for signal conditioning |
| **Sentiment** | News and social sentiment signal integration |
| **Fair Value** | Micro-price, depth imbalance, and fair-value model signals |
| **Structural** | Complement parity, cross-market consistency, relative value |
| **Composite** | Weighted combination of signal families after validation |
