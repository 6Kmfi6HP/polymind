# Getting Started

This guide walks you through installing Polymind and running your first
market-making strategy.

## Prerequisites

- Python 3.10 or later
- A Polymarket account (for live trading)
- API credentials (for non-public endpoints)

## Installation

### From PyPI

```bash
pip install polymind
```

With extra dependencies:

```bash
# AI providers (OpenAI, Anthropic, Google)
pip install "polymind[ai]"

# Data analysis (pandas, numpy)
pip install "polymind[data]"

# Database persistence (SQLite)
pip install "polymind[db]"

# Everything
pip install "polymind[full]"
```

### From Source

```bash
git clone https://github.com/your-org/polymind.git
cd polymind
pip install -e ".[dev]"
```

## Quick Start

### 1. Verify Installation

```bash
polymind --help
pm --help  # shortcut alias
```

### 2. List Available Strategies

```bash
polymind strategies
```

This shows all registered strategies and their descriptions.

### 3. Check System Status

```bash
polymind status
```

Shows configuration status, available adapters, and connectivity checks.

### 4. Run a Strategy (Dry-Run Mode)

```bash
polymind run "AMM market making, 100 USDC budget, depth 0.05" --dry-run
```

The `--dry-run` flag simulates execution without placing real orders.

```bash
polymind run --strategy momentum --dry-run
```

### 5. Run Configuration Setup

```bash
polymind setup
```

Walks through interactive configuration for API keys, wallet credentials,
and strategy parameters.

## Using the Strategy Generator

Polymind can parse natural language strategy descriptions into typed
configuration:

```bash
polymind run "Cross-sectional momentum on 30 markets, lookback 7d, top decile, 4h hold, 500 USDC budget"
```

This uses the AI Studio's strategy generator to convert your description
into a validated `StrategyConfig` and execute it.

## Running Tests

```bash
# All tests
pytest tests/ -v

# Specific test file
pytest tests/test_core.py -v

# With coverage
pytest --cov=polymind tests/
```

## Next Steps

1. Read the [Architecture](../architecture.md) overview to understand the system design
2. Browse the [API Reference](../api/core.md) for detailed module documentation
3. Explore the strategy implementations in `polymind/strategies/`
4. Set up your Polymarket API credentials with `polymind setup`

## Project Layout

```
polymind/
├── polymind/          # Main package
│   ├── core/          # Framework contracts (agent, intents, strategy, risk)
│   ├── execution/     # Order lifecycle, fill simulation
│   ├── strategies/    # Market-making and factor strategy implementations
│   ├── polymarket/    # Polymarket integration adapters
│   ├── factors/       # Factor engine (pipeline, features, filters)
│   ├── agents/        # AI provider adapters
│   ├── risk/          # Risk gates and limits
│   ├── backtesting/   # Backtest engine and execution models
│   └── studio/        # AI strategy generator and optimizer
├── docs/              # Documentation
└── tests/             # Test suite
```
