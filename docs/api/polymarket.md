# Polymarket Module

Polymarket CLOB integration adapters.

## Components

- **client.py** — `PolymarketClient` CLOB SDK wrapper
- **websocket.py** — `PolymarketWebSocketAdapter` with auto-reconnect
- **data_api.py** — `PolymarketDataAPI` for Gamma API
- **contracts.py** — `ContractsGateway` for split/merge/redeem
- **signer.py** — `Signer` with AuthTier (PUBLIC/API_KEY/WALLET)
- **metrics.py** — `AdapterMetrics` counters and histograms
