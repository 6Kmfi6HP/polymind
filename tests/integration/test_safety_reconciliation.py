"""Integration tests: KillSwitch + Preflight + Reconciliation."""

from __future__ import annotations

import pytest

from polymind.utils.killswitch import KillSwitch
from polymind.utils.preflight import PreflightChecker, PreflightSeverity
from polymind.reconciliation.fills import FillReconciler, FillReconciliationRecord, ReconciliationStatus
from polymind.reconciliation.recovery import RecoveryManager, RecoveryAction
from polymind.core.fills import FillEvent, FillSource
from polymind.core.intents import OrderSide
from datetime import datetime


class TestKillSwitch:
    def test_default_not_triggered(self) -> None:
        ks = KillSwitch()
        assert not ks.is_triggered()

    def test_trigger_file(self) -> None:
        import tempfile, os
        ks = KillSwitch(file_path="/tmp/_test_kill_int")
        assert not ks.is_triggered()
        ks.trigger()
        assert ks.is_triggered()
        ks.release()
        assert not ks.is_triggered()
        if os.path.exists("/tmp/_test_kill_int"):
            os.remove("/tmp/_test_kill_int")


class TestPreflight:
    def test_config_check(self) -> None:
        c = PreflightChecker()
        r = c.check_config({"key": "val"}, ["key", "missing"])
        assert not r.passed

    def test_credentials(self) -> None:
        c = PreflightChecker()
        r = c.check_credentials(True, False)
        assert r.severity == PreflightSeverity.WARN


class TestReconciliation:
    def test_record_construction(self) -> None:
        r = FillReconciliationRecord(market_id="0xabc", identity_string="i", expected_fill_size=100.0,
            expected_fill_price=0.5, actual_fill_size=100.0, actual_fill_price=0.5,
            status=ReconciliationStatus.MATCHED, discrepancy=0.0, timestamp=datetime(2026, 1, 1))
        assert r.status == ReconciliationStatus.MATCHED

    def test_recovery_init(self) -> None:
        rm = RecoveryManager()
        assert rm._max_retries == 3

    @pytest.mark.asyncio
    async def test_reconciler_init(self) -> None:
        r = FillReconciler()
        assert r is not None
