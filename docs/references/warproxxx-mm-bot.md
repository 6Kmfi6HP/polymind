# warproxxx-mm-bot Reference Evidence

**Source:** `/home/debian/pmdata/warproxxx-mm-bot`
**Role:** Event-driven market-making behavior and risk reference

## Evidence checked

- `README.md:9-22,59-76,109-136,150`
- `main.py:79-115`
- `poly_data/websocket_handlers.py:9-97`
- `poly_data/data_processing.py:38-157`
- `trading.py:20-79,82-123,128-186,188-344,346-455,465-471`
- `poly_data/trading_utils.py:28-190`
- `poly_data/data_utils.py:7-148`
- `poly_data/global_state.py:9-27`
- `poly_data/polymarket_client.py:103-140,263-317`
- `poly_merger/README.md:17-24`
- `poly_stats/account_stats.py:16-135`
- `poly_utils/google_utils.py:11-120`

## Copy

- Event-driven shell with market and user WebSocket ingestion.
- Deterministic quote and sizing formulas once fed by immutable snapshots.
- Explicit concepts for reverse-position checks, stop-loss, cooldown, and merge eligibility.
- Reporting as a read-model outside the decision loop.

## Do not copy blindly

- Module-level mutable global state for books, positions, and orders.
- Business logic inside WebSocket callbacks.
- Monolithic trading file that mixes policy, persistence, execution, merge, and cooldown.
- File-backed cooldown state embedded in core decision logic.
- Reporting or Google Sheets dependencies leaking into trading core.

## Polymind roadmap implication

Event MM needs normalized event adapters, pure decision services, explicit risk
states, serialized per-market command execution, and separate reporting adapters.
