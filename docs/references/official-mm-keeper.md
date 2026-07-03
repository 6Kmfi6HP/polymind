# pm-official-mm-keeper Reference Evidence

**Source:** `/home/debian/pmdata/pm-official-mm-keeper`
**Role:** Official AMM/Bands market-making reference

## Evidence checked

- `README.md:10-13,41-53`
- `poly_market_maker/strategy.py:15-106`
- `poly_market_maker/orderbook.py:67-120,126-129,200-265`
- `poly_market_maker/strategies/amm.py:9-190`
- `poly_market_maker/strategies/amm_strategy.py:9-99`
- `poly_market_maker/strategies/bands.py:9-317`
- `poly_market_maker/strategies/bands_strategy.py:9-98`
- `docs/strategies/amm.md`, `docs/strategies/bands.md`
- `config/amm.json`, `config/bands.json`
- `tests/test_amm_manager.py`, `test_band.py`, `test_order_type.py`, `test_strategy.py`

## Copy

- Snapshot to expected-orders to executor split.
- AMM/Bands math isolated from CLOB transport.
- Strategy invariant tests for ladder symmetry, band overlap, cancel/replace behavior, and band fill order.
- Config and docs that mirror each strategy contract.

## Do not copy blindly

- Positional unpacking from JSON object values.
- In-place mutation of band values as implicit behavior.
- Universal order identity based only on price, side, and token; that equality is useful for ladder netting but not for fill auditing.
- Binary-market complement assumptions in shared core modules.

## Polymind roadmap implication

AMM and Bands should be ported as pure strategy engines first. Executor wiring,
order reconciliation, and SDK transport belong in later adapter work.
