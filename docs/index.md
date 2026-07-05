# Polymind

**AI-Native Market Making for Polymarket**

Write strategies in English, let AI execute them.

---

## What is Polymind?

Polymind is a unified, AI-native market-making and cross-sectional factor framework
for [Polymarket](https://polymarket.com), the leading decentralized prediction
market platform.

It merges **eight existing Polymarket projects** (four market-making bots and four
factor research/backtesting frameworks) into one coherent system where:

- **Strategies are described in natural language** and assembled from modular components
- **Execution is exchange-aware**: limit orders model queue position, latency, partial fills,
  and adverse selection — no midpoint fantasy fills
- **Risk gates** sit between strategy intents and execution, enforcing limits before orders
  reach the exchange
- **Backtesting uses executable prices**: CLOB bid/ask, not Gamma midpoint prices

## Key Features

- **Agent Loop**: `observe -> decide -> act` framework with configurable loop intervals and risk management
- **Strategy Engine**: NL parsing, strategy registry, factor/workflow registries
- **Market-Making Policies**: AMM concentrated liquidity, Bands strategy, Classic MM
- **Trading Workflows**: Maker Rebate, Event MM, Sniper, Copy Trade
- **Factor Framework**: Cross-sectional momentum, regime detection, sentiment analysis,
  fair-value/microstructure, structural relative-value
- **Polymarket Integration**: CLOB API, WebSocket, Gamma/Data API, smart contracts,
  signing and authentication
- **Backtesting Engine**: Walk-forward validation, execution-aware simulation,
  portfolio and factor backtests
- **Paper Trading**: Sandbox runtime shared by all strategies, with fill simulation
  and position tracking
- **AI Studio**: Natural language to typed strategy configuration, parameter optimization

## Project Status

Polymind has completed **44+ development phases** covering the full architecture:

- **Core Framework**: Agent loop, domain contracts, strategy engine, risk gates, plugin system
- **7 Trading Strategies**: AMM, Bands, Classic MM, Maker Rebate, Event MM, Sniper, Copy Trade
- **Factor Framework**: Cross-sectional momentum, volatility, sentiment, fair-value, regime detection
- **Multi-Venue**: Polymarket CLOB, Kalshi, Limitless adapters (ExchangeAdapter ABC)
- **AI Studio**: NL-to-strategy generation, factor discovery with LLM, parameter optimization
- **Operations**: CLI, daemon mode, reports dashboard, HTML gallery, plugin management
- **QA**: 1685+ tests, 97% coverage, 0 mypy errors, CI/CD with pre-commit

See [Architecture](architecture.md) for the full roadmap and [Current State](architecture/current-state.md) for detailed status.

## Quick Start

```bash
# Install
pip install polymind

# Run a strategy (dry-run)
polymind run --strategy momentum --dry-run

# Interactive shell
polymind shell
```

See the [Getting Started Guide](guides/getting-started.md) for detailed instructions.

## License

MIT
