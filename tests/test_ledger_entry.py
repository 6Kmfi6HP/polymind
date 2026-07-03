"""
Tests for LedgerEntry and EntryType.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from polymind.core.ledger import EntryType, LedgerEntry


class TestEntryType:
    def test_enum_values(self):
        assert EntryType.FILL != EntryType.FEE
        assert EntryType.MERGE != EntryType.SPLIT

    def test_correction_type_exists(self):
        assert EntryType.CORRECTION in EntryType

    def test_all_types_defined(self):
        expected = {
            "FILL", "FEE", "MERGE", "SPLIT", "REDEEM",
            "CASH_ADJUSTMENT", "CORRECTION",
        }
        assert {e.name for e in EntryType} == expected


class TestLedgerEntry:
    def test_minimal_construction(self):
        now = datetime.now(timezone.utc)
        entry = LedgerEntry(
            entry_id="ledger-001",
            entry_type=EntryType.FILL,
            timestamp=now,
            market_id="0xabc",
            description="Bought 10 YES @ 0.85",
            delta_cash=-8.51,
            delta_position=10.0,
            position_after=10.0,
            cash_after=991.49,
        )
        assert entry.entry_id == "ledger-001"
        assert entry.entry_type == EntryType.FILL
        assert entry.timestamp == now
        assert entry.market_id == "0xabc"
        assert entry.delta_cash == -8.51
        assert entry.delta_position == 10.0
        assert entry.position_after == 10.0
        assert entry.cash_after == 991.49
        assert entry.fill_ref is None
        assert entry.supersedes is None

    def test_fill_reference(self):
        now = datetime.now(timezone.utc)
        entry = LedgerEntry(
            entry_id="ledger-002",
            entry_type=EntryType.FILL,
            timestamp=now,
            market_id="0xabc",
            description="Sold 5 YES @ 0.90",
            delta_cash=4.49,
            delta_position=-5.0,
            position_after=5.0,
            cash_after=995.98,
            fill_ref="fill-001",
        )
        assert entry.fill_ref == "fill-001"

    def test_supersedes_chain(self):
        now = datetime.now(timezone.utc)
        original = LedgerEntry(
            entry_id="ledger-001",
            entry_type=EntryType.FILL,
            timestamp=now,
            market_id="0xabc",
            description="Original entry",
            delta_cash=-8.50,
            delta_position=10.0,
            position_after=10.0,
            cash_after=991.50,
        )
        corrected = LedgerEntry(
            entry_id="ledger-003",
            entry_type=EntryType.CORRECTION,
            timestamp=now,
            market_id="0xabc",
            description="Corrected fee",
            delta_cash=-8.51,
            delta_position=10.0,
            position_after=10.0,
            cash_after=991.49,
            supersedes="ledger-001",
        )
        assert corrected.supersedes == original.entry_id

    def test_cash_adjustment_entry(self):
        now = datetime.now(timezone.utc)
        entry = LedgerEntry(
            entry_id="ledger-004",
            entry_type=EntryType.CASH_ADJUSTMENT,
            timestamp=now,
            market_id="GLOBAL",
            description="Deposit 500 USDC",
            delta_cash=500.0,
            delta_position=0.0,
            position_after=0.0,
            cash_after=1500.0,
        )
        assert entry.entry_type == EntryType.CASH_ADJUSTMENT
        assert entry.delta_position == 0.0
