# Third-Party Code, Provenance & License Boundaries

This file records every external project whose code, ideas, or structure
influenced Polymind, along with license compatibility verification.

## Purpose

- Track provenance of all third-party code copied, adapted, or referenced
- Verify license compatibility with our MIT license
- Ensure LGPL-scoped code is isolated behind adapter boundaries
- Provide audit trail for compliance

## Projects

### Market-Making Bots

| Project | Source | License | Files Derived / Adapted | Status |
|---------|--------|---------|------------------------|--------|
| probablyprofit-ai-framework | [randomness11/probablyprofit](https://github.com/randomness11/probablyprofit) | MIT | polymind/core/agent.py, polymind/core/engine.py, polymind/risk/* | ✅ Compatible |
| pm-official-mm-keeper | [Polymarket/poly-market-maker](https://github.com/Polymarket/poly-market-maker) | MIT | polymind/strategies/* (AMM, Bands pricing/sizing) | ✅ Compatible |
| warproxxx-mm-bot | [warproxxx/poly-maker](https://github.com/warproxxx/poly-maker) | MIT | polymind/workflows/event_mm/* | ✅ Compatible |
| pm-terminal-all-in-one | [direkturcrypto/polymarket-terminal](https://github.com/direkturcrypto/polymarket-terminal) | MIT | polymind/workflows/{maker_rebate,sniper,copy_trade}/* | ✅ Compatible |

### Factor Research & Backtesting

| Project | Source | License | Files Derived / Adapted | Status |
|---------|--------|---------|------------------------|--------|
| polymarket-cross-sectional-momentum | [recallnet/polymarket-cross-sectional-momentum](https://github.com/recallnet/polymarket-cross-sectional-momentum) | MIT | polymind/factors/*, polymind/backtesting/*, polymind/storage/price_store.py | ✅ Compatible |
| Polymarket-Edge-Research | [oscarc17/Polymarket-Edge-Research](https://github.com/oscarc17/Polymarket-Edge-Research) | MIT | polymind/backtesting/factor_bt.py, polymind/studio/factor_analysis.py | ✅ Compatible |
| prediction-market-backtesting | [evan-kolberg/prediction-market-backtesting](https://github.com/evan-kolberg/prediction-market-backtesting) | MIT (core) / LGPL (extensions) | polymind/backtesting/* (data loading patterns only) | ⚠️ Partial — LGPL extensions not copied; adapter boundary documented in architecture.md |
| polymarket-quant | [chiantsii/polymarket-quant](https://github.com/chiantsii/polymarket-quant) | MIT | polymind/strategies/fair_value*, polymind/execution/fill_model.py | ✅ Compatible |

## License Compatibility

- All direct dependencies are MIT-licensed, compatible with this project's MIT license.
- The `prediction-market-backtesting` project (Evan Kolberg) contains NautilusTrader-adjacent
  data-loading code and LGPL-scoped extension concerns. Only MIT-licensed data-loading
  patterns were referenced; no LGPL code was copied into this repository.
- See `docs/architecture.md` section "LGPL Boundary" for isolation strategy documentation.

## Verification

Each entry was verified at the time of code import:
- Source URL confirmed active
- License file present in source repository
- License type confirmed compatible with MIT (or isolated if LGPL)
- Files derived from the project are listed with the specific module path

Last verified: 2026-07-05
