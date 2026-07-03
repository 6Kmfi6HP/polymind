# probablyprofit-ai-framework Reference Evidence

**Source:** `/home/debian/pmdata/probablyprofit-ai-framework`
**Role:** AI trading framework reference

## Evidence checked

- `README.md:28-54,112-133,154-176,196-288,450-468`
- `docs/architecture.md:13-45,96-123,132-136`
- `probablyprofit/__init__.py:19-39,81-102`
- `probablyprofit/agent/base.py:245-311,363-404,576-774`
- `probablyprofit/agent/strategy.py:15-24,36-463`
- `probablyprofit/risk/manager.py:1-95,342-845`
- `probablyprofit/storage/models.py`, `repositories.py`, `database.py`
- `probablyprofit/backtesting/engine.py`, `metrics.py`
- `probablyprofit/config.py:1-8,20-23,233-357,471-507,629-704`
- `probablyprofit/cli/main.py:33-124,141-283`

## Copy

- Composition-root CLI that wires config, storage, risk, strategy, client, and agent.
- Template-method agent loop with explicit observe, decide, act, shutdown, and persistence hooks.
- Risk as its own subsystem: limits, sizing, stop-loss, drawdown, and recovery state.
- Persistence split into models, repositories, and database/session management.
- Backtesting split into simulation engine and metrics module.
- Small public facade with lazy imports.

## Do not copy blindly

- Hidden singleton dependencies that make tests depend on global runtime state.
- Over-broad public exports before modules are implemented.
- Strategy abstractions that blur market selection, prompt generation, execution, and storage.

## Polymind roadmap implication

Polymind should keep CLI wiring at the edge and core strategy/risk/storage logic
behind explicit boundaries. Public documentation must not advertise a module as
available before it exists and is wired through a tested boundary.
