# Phase 17: ContractsGateway Real Web3 Implementation — Design

**Status:** Design
**Date:** 2026-07-04

## Overview

Replace ContractsGateway stub (all methods `NotImplementedError`) with real Web3.py
integration for on-chain Polymarket operations: split, merge, redeem, balance reads,
and approvals.

## Architecture

```
ContractsGateway
  │
  ├── connect()         → Web3(provider)
  ├── get_onchain_balance(token_id) → OnChainBalance
  ├── split(condition_id, amount)  → TransactionResult
  ├── merge(condition_id, amount)  → TransactionResult
  ├── redeem(condition_id, outcome_index, amount) → TransactionResult
  ├── approve_usdc(amount)         → TransactionResult
  ├── approve_exchange(token_id)   → TransactionResult
  └── close()                      → release
```

## Domain Types

- `OnChainBalance` — token_id, balance (int), usdc_balance (float)
- `TransactionResult` — tx_hash, status, block_number, gas_used, gas_price_gwei

## Contract Addresses (mainnet)

- USDC: `0x2791Bca1f2de4661ED88A30C99A7a9449Aa84174`
- CTF Exchange: `0x4bFb41d5B3570DeFd03C39a9A4D8dE6Bd8Bd8987`
- ERC-1155: Standard interface via CTF Exchange
