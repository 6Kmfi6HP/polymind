# pm-terminal-all-in-one Reference Evidence

**Source:** `/home/debian/pmdata/pm-terminal-all-in-one`
**Role:** Maker rebate, sniper, copy-trade, and fill-recovery workflow reference

## Evidence checked

- `README.md:12-30,50-80,116-185`
- `src/config/index.js:4-210`
- `src/services/client.js:1-80`
- `src/services/ctf.js:108-123,253-294,297-433,645-832`
- `src/services/wsWatcher.js:1-220`
- `src/services/position.js:1-120`
- `src/services/redeemer.js:1-220`
- `src/services/executor.js:17-23,93-174,182-452`
- `src/services/mmWsFillWatcher.js:1-220`
- `src/services/mmDetector.js:1-192`
- `src/services/mmExecutor.js:313-623,910-1041,1055-1136`
- `src/services/makerRebateExecutor.js:17-31,195-245,317-389,614-934`
- `src/maker-mm-bot.js:1-200`
- `src/services/sniperDetector.js:1-220`
- `src/services/sniperExecutor.js:1-120`
- `src/services/schedule.js:1-120`

## Copy

- Separate bounded workflows for maker rebate, sniper, copy trade, and classic MM.
- On-chain balance verification for ghost fills, partial fills, merge/redeem flows, and recovery.
- Per-market or per-asset serialization before placing or canceling orders.
- Dedicated wallet/chain gateway for approvals, split, merge, redeem, and Safe transactions.
- Deterministic market discovery and session scheduling where applicable.

## Do not copy blindly

- Global mutable shared config that is changed by entrypoints at runtime.
- JSON file state embedded directly in business services instead of repository ports.
- Callback injection to work around circular imports.
- Combining Safe signing, approvals, order policy, persistence, and retries in one service.
- Treating maker rebate, sniper, copy trade, and classic MM as flags on a generic trader.

## Polymind roadmap implication

Each terminal workflow needs its own state-machine document, explicit persistence
ports, and recovery paths before implementation. Shared infrastructure belongs
behind ports: CLOB client, fill stream, wallet transaction executor, chain
balance reader, position store, and scheduler.
