# Phase 17: ContractsGateway Real Web3 Implementation — Implementation Plan

**Goal:** Replace ContractsGateway stub (all NotImplementedError) with real Web3.py integration.

---

### Task 1: Rewrite contracts.py with Web3 implementation

**File:** `polymind/polymarket/contracts.py` (rewrite)

Add domain types (from spec + existing):
- `OnChainBalance` (token_id, balance, usdc_balance, decimals)
- `TransactionResult` (tx_hash, status, block_number, gas_used, gas_price_gwei)
- Keep existing: `SplitResult`, `MergeResult`, `RedeemResult`, `TokenBalance`, `ContractsConfig`

Rewrite `ContractsGateway`:
- Constructor: config + optional signer
- `connect()` — init Web3 provider
- `get_onchain_balance(token_id)` → OnChainBalance
- `split(condition_id, amount, outcomes)` → TransactionResult
- `merge(condition_id, amount, outcomes)` → TransactionResult
- `redeem(condition_id, outcome_index, amount)` → TransactionResult
- `approve_usdc(amount)` → TransactionResult
- `approve_exchange(token_id, amount)` → TransactionResult
- `close()` — release

Keep existing backward compat methods (balance_of, approve) that delegate.

---

### Task 2: Rewrite test_contracts.py

**File:** `tests/polymarket/test_contracts.py`

Replace subclass-based tests with mock-based tests (mock Web3).

---

### Task 3: Verify

- Run full test suite
- Run lint (ruff)
