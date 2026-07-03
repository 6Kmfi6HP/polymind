# Getting Started

## Installation

```bash
pip install -e .
```

## CLI Usage

```bash
# List available strategies
polymind strategies

# Show system status
polymind status

# Run configuration setup
polymind setup
```

## Running a Strategy

```bash
polymind run "AMM market making, 100 USDC budget, depth 0.05"
```

## Running Tests

```bash
pytest tests/ -v
```
