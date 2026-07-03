# Core Module

Base contracts for the Polymind framework.

## Components

- **agent.py** — `BaseAgent` ABC with observe/decide/act/reflect
- **config.py** — Configuration management
- **intents.py** — `OrderIntent`, `CancelIntent`, `StrategyIntent`, `IntentExecutor`
- **strategy.py** — `BaseStrategy`, `MarketMakingPolicy`, `FactorSignalModel`
- **fills.py** — `FillEvent`, `FillSource`
- **ledger.py** — `LedgerEntry`, `EntryType`
- **portfolio.py** — `PortfolioTarget`, `PositionDirection`
- **risk.py** — `RiskDecision`, `RiskGate`, `RiskContext`
- **workflows.py** — `WorkflowCommand`, `CommandType`
