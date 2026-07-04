# Phase 15: Polymarket Adapter Errors & Signer Enhancements — Design

**Status:** Design
**Date:** 2026-07-04

## Overview

Polymarket adapters currently have no error hierarchy and the Signer is missing
EIP-712 signing and API key derivation. This phase adds the exception hierarchy
defined in the Phase 1 spec and enhances the Signer with real `py-clob-client`
integration.

## Changes

### 1. Error Hierarchy — new file `polymind/polymarket/errors.py`

```python
class PolymarketError(Exception):          # base
class AuthenticationError(PolymarketError)  # invalid/expired credentials
class InsufficientAuthError(PolymarketError) # operation requires higher tier
class MarketNotFoundError(PolymarketError)  # unknown market/token
class OrderRejectedError(PolymarketError)   # CLOB rejected order
class RateLimitError(PolymarketError)       # HTTP 429
class ConnectionError(PolymarketError)      # network failure
class ContractError(PolymarketError)        # on-chain revert
class NonceTooLowError(ContractError)
class InsufficientGasError(ContractError)
```

### 2. Signer Enhancement — `polymind/polymarket/signer.py`

- `sign_typed_data()` — uses `eth_account` to sign EIP-712 typed data
- `derive_api_key()` — wraps `ClobClient.create_or_derive_api_creds`
- `sign_hash()` — signs arbitrary hash with wallet key

### 3. Existing adapter tests remain passing

## Testing

- Unit tests for all error types
- Unit tests for sign_typed_data (with mock key)
- Unit tests for derive_api_key (with mock ClobClient)
- All 1044 existing tests remain passing
