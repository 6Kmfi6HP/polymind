# Phase 15: Polymarket Adapter Errors & Signer — Implementation Plan

**Goal:** Add adapter error hierarchy and enhance Signer with real signing/derivation.

---

### Task 1: Error hierarchy

**Files:**
- Create: `polymind/polymarket/errors.py`
- Test: `tests/polymarket/test_errors.py`

Implement all error classes from the Phase 1 spec:
- `PolymarketError` (base)
- `AuthenticationError`, `InsufficientAuthError`, `MarketNotFoundError`
- `OrderRejectedError`, `RateLimitError`, `ConnectionError`
- `ContractError`, `NonceTooLowError`, `InsufficientGasError`

RateLimitError has a `retry_after` field. All others are simple subclasses.

---

### Task 2: Signer enhancements

**File:** `polymind/polymarket/signer.py` (edit)
**Test:** `tests/polymarket/test_signer.py` (edit)

Implement these methods on Signer:

1. `sign_typed_data(domain, message_types, message) -> str`:
   - Uses `eth_account.messages.encode_typed_data` + `Account.sign_message`
   - Returns hex signature (0x-prefixed)
   - Raises `InsufficientAuthError` if tier < WALLET

2. `derive_api_key(host) -> ApiKeyCredentials`:
   - Creates temporary `ClobClient` instance, calls `create_or_derive_api_creds`
   - Returns `ApiKeyCredentials`
   - Raises `InsufficientAuthError` if tier < WALLET

3. `sign_hash(message_hash) -> str`:
   - Signs arbitrary bytes hash using wallet key
   - Returns hex signature

---

### Task 3: Verify

- Run full test suite
- Run lint (ruff)
