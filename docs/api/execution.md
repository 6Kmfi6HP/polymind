# Execution Module

Order execution and fill simulation.

## Components

- **executor.py** — `PaperExecutor`, `OrderRecord`, `PositionRecord`
- **order_identity.py** — `OrderIdentity` (frozen, deterministic)
- **fill_model.py** — `FillModel`, `FillModelConfig`, `MarketSnapshot`, `FillResult`
- **serializer.py** — `OrderSerializer`, `SerializerConfig`, `SerializedOrder`
