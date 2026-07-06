"""Integration tests: KillSwitch + Preflight + PaperExecutor + Ledger + Reconciliation + WebSocket events.

Covers three end-to-end scenarios:

1. Safety integration — PreflightChecker validates configuration before
   PaperExecutor starts; KillSwitch serves as an emergency stop; a guard
   wrapper rejects execution once the switch is triggered.

2. LedgerStore + Reconciliation integration — PaperExecutor fills produce
   LedgerEntries that get persisted by LedgerStore; BalanceReconciler
   compares local position state against on-chain snapshots; RecoveryManager
   assesses missing / mismatched fills and generates recovery actions.

3. WebSocket + MarketEvent pipeline — MarketEvent objects are created,
   streamed through an async generator (simulating the WebSocket adapter),
   and integrated into the FillReconciler cross-check flow.
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

import pytest

from polymind.core.fills import FillEvent, FillSource
from polymind.core.intents import (
    IntentExecutor,
    OrderIntent,
    OrderSide,
    StrategyIntent,
)
from polymind.core.ledger import EntryType
from polymind.execution.executor import PaperExecutor
from polymind.execution.fill_model import (
    MarketSnapshot,
)
from polymind.polymarket.websocket import (
    MarketEvent,
    PolymarketWebSocketAdapter,
    WebSocketChannel,
    WebSocketConfig,
)
from polymind.reconciliation.balances import BalanceReconciler, BalanceSnapshot
from polymind.reconciliation.fills import (
    FillReconciler,
    FillReconciliationRecord,
    ReconciliationStatus,
)
from polymind.reconciliation.recovery import RecoveryAction, RecoveryManager
from polymind.storage.database import DatabaseConfig
from polymind.storage.ledger import LedgerStore
from polymind.utils.killswitch import KillSwitch
from polymind.utils.preflight import PreflightChecker, PreflightReport, PreflightSeverity

# ─────────────────────────────────────────────────────────────────────────────
# Scenario 1 — KillSwitch + Preflight + PaperExecutor safety integration
# ─────────────────────────────────────────────────────────────────────────────


class TestKillSwitchSafety:
    """KillSwitch acts as an emergency circuit-breaker for PaperExecutor."""

    def test_default_state_is_safe(self) -> None:
        """A newly created KillSwitch is not triggered."""
        ks = KillSwitch()
        assert not ks.is_triggered()

    def test_trigger_and_release_in_process(self) -> None:
        """Triggering the in-process flag makes is_triggered() return True."""
        ks = KillSwitch()
        ks.trigger()
        assert ks.is_triggered()
        ks.release()
        assert not ks.is_triggered()

    def test_file_sentinel_trigger(self) -> None:
        """A KillSwitch with a file path creates/removes a sentinel file."""
        import os
        import tempfile

        with tempfile.NamedTemporaryFile(suffix=".kill", delete=False) as f:
            path = f.name
        os.remove(path)

        ks = KillSwitch(file_path=path)
        assert not ks.is_triggered()

        ks.trigger()
        assert ks.is_triggered()
        assert os.path.exists(path)

        ks.release()
        assert not ks.is_triggered()
        assert not os.path.exists(path)

    def test_trigger_is_idempotent(self) -> None:
        """Calling trigger() multiple times stays triggered."""
        ks = KillSwitch()
        ks.trigger()
        ks.trigger()
        assert ks.is_triggered()

    def test_release_is_idempotent(self) -> None:
        """Calling release() on a released switch stays released."""
        ks = KillSwitch()
        ks.release()
        ks.release()
        assert not ks.is_triggered()

    def test_env_var_triggers(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """Setting the configured env var to '1' triggers the switch."""
        monkeypatch.setenv("POLYMIND_KILL", "1")
        ks = KillSwitch(env_var="POLYMIND_KILL")
        assert ks.is_triggered()

    def test_env_var_true_case_insensitive(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """'TRUE' and 'true' both trip the kill switch."""
        monkeypatch.setenv("POLYMIND_KILL", "TRUE")
        ks = KillSwitch(env_var="POLYMIND_KILL")
        assert ks.is_triggered()

    def test_env_var_empty_not_triggered(self, monkeypatch: pytest.MonkeyPatch) -> None:
        """An empty env var does NOT trigger the switch."""
        monkeypatch.setenv("POLYMIND_KILL", "")
        ks = KillSwitch(env_var="POLYMIND_KILL")
        assert not ks.is_triggered()


class TestPreflightIntegration:
    """PreflightChecker validates readiness before PaperExecutor starts."""

    def test_config_check_passes_with_required_keys(self) -> None:
        """A config dict with all required keys produces a PASS result."""
        config = {"platform": "polymarket", "initial_capital": 10_000.0, "extra": True}
        result = PreflightChecker.check_config(config, ["platform", "initial_capital"])
        assert result.passed
        assert result.severity == PreflightSeverity.PASS

    def test_config_check_fails_when_key_missing(self) -> None:
        """A config dict missing a required key produces a FAIL result."""
        config = {"platform": "polymarket"}
        result = PreflightChecker.check_config(config, ["platform", "initial_capital"])
        assert not result.passed
        assert result.severity == PreflightSeverity.FAIL
        assert "initial_capital" in result.message

    def test_config_check_fails_when_key_is_none(self) -> None:
        """A required key set to None is treated as missing."""
        config = {"platform": "polymarket", "initial_capital": None}
        result = PreflightChecker.check_config(config, ["platform", "initial_capital"])
        assert not result.passed

    def test_credentials_pass_when_both_present(self) -> None:
        """Having both API key and private key yields a PASS."""
        result = PreflightChecker.check_credentials(has_api_key=True, has_private_key=True)
        assert result.passed
        assert result.severity == PreflightSeverity.PASS

    def test_credentials_warn_when_api_key_missing(self) -> None:
        """Missing only the API key yields a WARN (not FAIL)."""
        result = PreflightChecker.check_credentials(has_api_key=False, has_private_key=True)
        assert not result.passed
        assert result.severity == PreflightSeverity.WARN

    def test_credentials_fail_when_both_missing(self) -> None:
        """Missing both credentials yields a FAIL."""
        result = PreflightChecker.check_credentials(has_api_key=False, has_private_key=False)
        assert not result.passed
        assert result.severity == PreflightSeverity.FAIL

    def test_run_all_aggregates_results(self) -> None:
        """run_all returns a PreflightReport containing all individual check results."""
        config = {"platform": "polymarket", "initial_capital": 10_000.0}
        report = PreflightChecker.run_all(config, has_api_key=True, has_private_key=True)
        assert isinstance(report, PreflightReport)
        assert len(report.results) == 2
        assert report.passed

    def test_run_all_fails_when_config_incomplete(self) -> None:
        """run_all returns passed=False when required config keys are missing."""
        config = {}
        report = PreflightChecker.run_all(config, has_api_key=True, has_private_key=True)
        assert not report.passed

    @pytest.mark.asyncio
    async def test_preflight_before_executor_start(self, paper_executor: PaperExecutor) -> None:
        """Preflight checks pass, then PaperExecutor starts and executes an order."""
        config = {"platform": "paper", "initial_capital": 10_000.0}
        report = PreflightChecker.run_all(config, has_api_key=True, has_private_key=True)
        assert report.passed

        intent = StrategyIntent(
            timestamp=datetime(2026, 1, 1),
            strategy_name="safe_test",
            orders=[OrderIntent(market_id="0xabc", side=OrderSide.BUY, price=0.51, size=10.0)],
        )
        result = await paper_executor.execute(intent)
        assert isinstance(result, dict)
        assert len(paper_executor.orders) == 1


class TestKillSwitchGuardsExecutor:
    """A guard wrapper that prevents PaperExecutor execution when KillSwitch is active."""

    @pytest.mark.asyncio
    async def test_guard_rejects_execution_when_triggered(
        self, paper_executor: PaperExecutor
    ) -> None:
        """A KillSwitch-aware guard raises or returns empty when the switch is flipped."""
        ks = KillSwitch()
        guard = _SafeExecutorGuard(executor=paper_executor, kill_switch=ks)

        # Normal operation
        intent = StrategyIntent(
            timestamp=datetime(2026, 1, 1),
            strategy_name="guard_test",
            orders=[OrderIntent(market_id="0xabc", side=OrderSide.BUY, price=0.51, size=10.0)],
        )
        result = await guard.execute(intent)
        assert "0xabc" in result

        # Kill switch triggered — execution refused
        ks.trigger()
        result2 = await guard.execute(intent)
        assert result2 == {}  # Guard returns empty when kill switch is active

    @pytest.mark.asyncio
    async def test_guard_rejects_dry_run_when_triggered(
        self, paper_executor: PaperExecutor
    ) -> None:
        """Even dry_run is blocked when the kill switch is active."""
        ks = KillSwitch()
        guard = _SafeExecutorGuard(executor=paper_executor, kill_switch=ks)

        intent = StrategyIntent(
            timestamp=datetime(2026, 1, 1),
            strategy_name="guard_test",
            orders=[OrderIntent(market_id="0xabc", side=OrderSide.BUY, price=0.51, size=10.0)],
        )

        result = await guard.dry_run(intent)
        assert result.get("dry_run") is True  # Normal dry run passes

        ks.trigger()
        result2 = await guard.dry_run(intent)
        assert result2 == {}  # Blocked


# ─────────────────────────────────────────────────────────────────────────────
# Scenario 2 — LedgerStore + Reconciliation integration
# ─────────────────────────────────────────────────────────────────────────────


class TestLedgerStoreIntegration:
    """PaperExecutor produces LedgerEntries; LedgerStore persists them; BalanceReconciler reconciles."""

    @pytest.mark.asyncio
    async def test_executor_creates_ledger_entries(self, paper_executor: PaperExecutor) -> None:
        """After a taker fill, PaperExecutor records a LedgerEntry with correct fields."""
        snapshot = MarketSnapshot(
            market_id="0xledger1",
            bid_price=0.50,
            bid_size=1000.0,
            ask_price=0.51,
            ask_size=1000.0,
            mid_price=0.505,
            timestamp=datetime(2026, 6, 1, 12, 0, 0),
        )
        intent = StrategyIntent(
            timestamp=datetime(2026, 6, 1, 12, 0, 0),
            strategy_name="ledger_test",
            orders=[OrderIntent(market_id="0xledger1", side=OrderSide.BUY, price=0.55, size=50.0)],
        )

        paper_executor._current_snapshot = snapshot
        await paper_executor.execute(intent)

        assert len(paper_executor.ledger) == 1
        entry = paper_executor.ledger[0]
        assert entry.entry_type == EntryType.FILL
        assert entry.market_id == "0xledger1"
        assert entry.delta_position == 50.0
        assert entry.delta_cash < 0  # Buying costs cash
        assert entry.fill_ref is not None
        assert entry.fill_ref.startswith("fill-")
        assert entry.position_after == 50.0

    @pytest.mark.asyncio
    async def test_ledger_store_persists_entries(self, paper_executor: PaperExecutor) -> None:
        """LedgerStore.append() persists a LedgerEntry; get_entries() returns it."""
        store = LedgerStore(DatabaseConfig(path=":memory:"))

        # Produce a fill via executor
        snapshot = MarketSnapshot(
            market_id="0xledger2",
            bid_price=0.40,
            bid_size=1000.0,
            ask_price=0.41,
            ask_size=1000.0,
            mid_price=0.405,
            timestamp=datetime(2026, 6, 1, 12, 0, 0),
        )
        intent = StrategyIntent(
            timestamp=datetime(2026, 6, 1, 12, 0, 0),
            strategy_name="persist_test",
            orders=[OrderIntent(market_id="0xledger2", side=OrderSide.BUY, price=0.44, size=30.0)],
        )

        paper_executor._current_snapshot = snapshot
        await paper_executor.execute(intent)

        # Persist the entry
        entry = paper_executor.ledger[0]
        await store.append(entry)

        # Read it back
        entries = await store.get_entries("0xledger2")
        assert len(entries) == 1
        restored = entries[0]
        assert restored.entry_id == entry.entry_id
        assert restored.market_id == "0xledger2"
        assert restored.delta_cash == entry.delta_cash
        assert restored.cash_after == entry.cash_after

        await store.close()

    @pytest.mark.asyncio
    async def test_ledger_store_tracks_cash_balance(self, paper_executor: PaperExecutor) -> None:
        """LedgerStore.get_cash_balance() returns the latest cash after."""
        store = LedgerStore(DatabaseConfig(path=":memory:"))

        snapshot = MarketSnapshot(
            market_id="0xledger3",
            bid_price=0.50,
            bid_size=1000.0,
            ask_price=0.51,
            ask_size=1000.0,
            mid_price=0.505,
            timestamp=datetime(2026, 6, 1, 12, 0, 0),
        )
        intent = StrategyIntent(
            timestamp=datetime(2026, 6, 1, 12, 0, 0),
            strategy_name="cash_test",
            orders=[OrderIntent(market_id="0xledger3", side=OrderSide.BUY, price=0.55, size=20.0)],
        )
        paper_executor._current_snapshot = snapshot
        await paper_executor.execute(intent)

        entry = paper_executor.ledger[0]
        await store.append(entry)

        balance = await store.get_cash_balance()
        assert balance == entry.cash_after
        assert balance < paper_executor.initial_cash  # Cash decreased after buy

        await store.close()

    @pytest.mark.asyncio
    async def test_ledger_store_pnl(self, paper_executor: PaperExecutor) -> None:
        """LedgerStore.get_pnl() sums delta_cash for a market."""
        store = LedgerStore(DatabaseConfig(path=":memory:"))

        snapshot = MarketSnapshot(
            market_id="0xledger4",
            bid_price=0.50,
            bid_size=1000.0,
            ask_price=0.51,
            ask_size=1000.0,
            mid_price=0.505,
            timestamp=datetime(2026, 6, 1, 12, 0, 0),
        )
        intent = StrategyIntent(
            timestamp=datetime(2026, 6, 1, 12, 0, 0),
            strategy_name="pnl_test",
            orders=[OrderIntent(market_id="0xledger4", side=OrderSide.BUY, price=0.51, size=20.0)],
        )
        paper_executor._current_snapshot = snapshot
        await paper_executor.execute(intent)

        entry = paper_executor.ledger[0]
        await store.append(entry)

        pnl = await store.get_pnl("0xledger4")
        assert pnl == entry.delta_cash  # delta_cash is negative for a buy

        await store.close()

    @pytest.mark.asyncio
    async def test_balance_reconciler_without_gateway(self) -> None:
        """BalanceReconciler returns a snapshot with no on-chain source."""
        reconciler = BalanceReconciler(contracts_gateway=None)
        snapshot = await reconciler.reconcile_balance(
            token_id="123", owner="0xuser", local_balance=100.0
        )
        assert isinstance(snapshot, BalanceSnapshot)
        assert snapshot.token_id == "123"
        assert snapshot.local_balance == 100.0
        assert snapshot.discrepancy == 100.0  # No on-chain data, discrepancy = local
        assert snapshot.onchain_balance == 0.0

    @pytest.mark.asyncio
    async def test_balance_reconciler_with_bridge(self, paper_executor: PaperExecutor) -> None:
        """BalanceReconciler reconciles PaperExecutor positions against a stubbed gateway."""
        snapshot = MarketSnapshot(
            market_id="0xrecon1",
            bid_price=0.50,
            bid_size=1000.0,
            ask_price=0.51,
            ask_size=1000.0,
            mid_price=0.505,
            timestamp=datetime(2026, 6, 1, 12, 0, 0),
        )
        intent = StrategyIntent(
            timestamp=datetime(2026, 6, 1, 12, 0, 0),
            strategy_name="recon_test",
            orders=[OrderIntent(market_id="0xrecon1", side=OrderSide.BUY, price=0.51, size=25.0)],
        )
        paper_executor._current_snapshot = snapshot
        await paper_executor.execute(intent)

        # Build local position dict from executor's positions
        local_positions: dict[str, float] = {}
        for pos in paper_executor.positions.values():
            local_positions[pos.market_id] = pos.size

        # Use a stub gateway that returns matching balance
        reconciler = BalanceReconciler(contracts_gateway=_StubContractsGateway({"0xrecon1": 25.0}))
        snapshots = await reconciler.reconcile_positions(local_positions, "0xuser")
        assert len(snapshots) == 1
        assert snapshots[0].discrepancy < 0.001

        await reconciler.close()

    @pytest.mark.asyncio
    async def test_recovery_manager_assesses_matched_fill(self) -> None:
        """RecoveryManager returns IGNORE for a matched reconciliation."""
        rm = RecoveryManager()
        fill = _make_fill(market_id="0xmatch", fill_id="f1", size=100.0, price=0.5)
        record = FillReconciliationRecord(
            market_id="0xmatch",
            identity_string="o1",
            expected_fill_size=100.0,
            expected_fill_price=0.5,
            actual_fill_size=100.0,
            actual_fill_price=0.5,
            status=ReconciliationStatus.MATCHED,
            discrepancy=0.0,
            timestamp=datetime(2026, 1, 1),
        )
        action = await rm.assess(fill, record)
        assert action == RecoveryAction.IGNORE

    @pytest.mark.asyncio
    async def test_recovery_manager_assesses_missing_fill(self) -> None:
        """RecoveryManager returns RETRY_ORDER for a missing fill."""
        rm = RecoveryManager()
        fill = _make_fill(market_id="0xmissing", fill_id="f2", size=100.0, price=0.5)
        record = FillReconciliationRecord(
            market_id="0xmissing",
            identity_string="o2",
            expected_fill_size=100.0,
            expected_fill_price=0.5,
            actual_fill_size=0.0,
            actual_fill_price=0.0,
            status=ReconciliationStatus.MISSING,
            discrepancy=100.0,
            timestamp=datetime(2026, 1, 1),
        )
        action = await rm.assess(fill, record)
        assert action == RecoveryAction.RETRY_ORDER

    @pytest.mark.asyncio
    async def test_recovery_manager_assesses_mismatched_fill(self) -> None:
        """RecoveryManager returns CANCEL_REPLACE for a mismatched fill."""
        rm = RecoveryManager()
        fill = _make_fill(market_id="0xmm", fill_id="f3", size=100.0, price=0.5)
        record = FillReconciliationRecord(
            market_id="0xmm",
            identity_string="o3",
            expected_fill_size=100.0,
            expected_fill_price=0.5,
            actual_fill_size=90.0,
            actual_fill_price=0.51,
            status=ReconciliationStatus.MISMATCHED,
            discrepancy=10.0,
            timestamp=datetime(2026, 1, 1),
        )
        action = await rm.assess(fill, record)
        assert action == RecoveryAction.CANCEL_REPLACE

    @pytest.mark.asyncio
    async def test_recovery_manager_escalates_after_max_retries(self) -> None:
        """RecoveryManager escalates when retry count exceeds max."""
        rm = RecoveryManager(max_retries=2)
        fill = _make_fill(market_id="0xesc", fill_id="f4", size=100.0, price=0.5)
        record = FillReconciliationRecord(
            market_id="0xesc",
            identity_string="o4",
            expected_fill_size=100.0,
            expected_fill_price=0.5,
            actual_fill_size=0.0,
            actual_fill_price=0.0,
            status=ReconciliationStatus.MISSING,
            discrepancy=100.0,
            timestamp=datetime(2026, 1, 1),
        )

        # First retry — still below max
        action1 = await rm.assess(fill, record)
        assert action1 == RecoveryAction.RETRY_ORDER
        await rm.execute(action1, fill)

        action2 = await rm.assess(fill, record)
        assert action2 == RecoveryAction.RETRY_ORDER
        await rm.execute(action2, fill)

        # Third time — max retries exceeded
        action3 = await rm.assess(fill, record)
        assert action3 == RecoveryAction.ESCALATE

    @pytest.mark.asyncio
    async def test_recovery_manager_execute_and_history(self) -> None:
        """Executing a recovery action records it in the manager's history."""
        rm = RecoveryManager()
        fill = _make_fill(market_id="0xhist", fill_id="f5", size=50.0, price=0.45)
        resolved = await rm.execute(RecoveryAction.RETRY_ORDER, fill)
        assert not resolved  # Retrying is never immediately resolved

        history = rm.get_history()
        assert len(history) == 1
        record = history[0]
        assert record.fill_id == "f5"
        assert record.market_id == "0xhist"
        assert record.action == RecoveryAction.RETRY_ORDER

    @pytest.mark.asyncio
    async def test_full_reconciliation_flow(self, paper_executor: PaperExecutor) -> None:
        """End-to-end: PaperExecutor fills → LedgerStore persists → RecoveryManager assesses.

        This test validates the complete pipeline from order execution through
        ledger persistence, balance reconciliation (via stub), and recovery
        assessment of the reconciliation results.
        """
        # ── 1. Setup ──
        store = LedgerStore(DatabaseConfig(path=":memory:"))

        # ── 2. Execute order via PaperExecutor ──
        snapshot = MarketSnapshot(
            market_id="0xfull-flow",
            bid_price=0.45,
            bid_size=2000.0,
            ask_price=0.46,
            ask_size=2000.0,
            mid_price=0.455,
            timestamp=datetime(2026, 6, 15, 10, 0, 0),
        )
        intent = StrategyIntent(
            timestamp=datetime(2026, 6, 15, 10, 0, 0),
            strategy_name="full_flow_test",
            orders=[
                OrderIntent(market_id="0xfull-flow", side=OrderSide.BUY, price=0.50, size=100.0)
            ],
        )
        paper_executor._current_snapshot = snapshot
        await paper_executor.execute(intent)

        # ── 3. Persist ledger entries ──
        for entry in paper_executor.ledger:
            await store.append(entry)

        # Verify persistence
        entries = await store.get_entries("0xfull-flow")
        assert len(entries) == 1

        persisted = entries[0]
        assert persisted.market_id == "0xfull-flow"
        assert persisted.entry_type == EntryType.FILL
        assert persisted.delta_position == 100.0

        # ── 4. Balance reconciliation ──
        bridge = _StubContractsGateway({"0xfull-flow": 100.0})
        reconciler = BalanceReconciler(contracts_gateway=bridge)

        local_positions: dict[str, float] = {
            mid: pos.size for mid, pos in paper_executor.positions.items()
        }
        snapshots = await reconciler.reconcile_positions(local_positions, "0xuser")
        assert len(snapshots) >= 1
        for snap in snapshots:
            assert snap.discrepancy < 0.001, f"Position {snap.token_id} out of sync"

        # ── 5. Recovery assessment on the fill ──
        rm = RecoveryManager(max_retries=3)
        fill_event = paper_executor.fills[0]

        recon_record = FillReconciliationRecord(
            market_id="0xfull-flow",
            identity_string=fill_event.fill_id,
            expected_fill_size=fill_event.size,
            expected_fill_price=fill_event.price,
            actual_fill_size=fill_event.size,
            actual_fill_price=fill_event.price,
            status=ReconciliationStatus.MATCHED,
            discrepancy=0.0,
            timestamp=fill_event.timestamp,
        )
        action = await rm.assess(fill_event, recon_record)
        assert action == RecoveryAction.IGNORE

        # Cleanup
        await store.close()
        await reconciler.close()
        await rm.close()


# ─────────────────────────────────────────────────────────────────────────────
# Scenario 3 — WebSocket + MarketEvent event handling
# ─────────────────────────────────────────────────────────────────────────────


class TestMarketEventPipeline:
    """MarketEvent creation, async-generator streaming, and integration with FillReconciler."""

    def test_market_event_construction(self) -> None:
        """A MarketEvent can be constructed with all required fields."""
        event = MarketEvent(
            market_id="0xws1",
            channel=WebSocketChannel.USER_FILL,
            event_type="fill",
            data={"size": "100.0", "price": "0.50"},
            timestamp=datetime(2026, 6, 1, 12, 0, 0),
        )
        assert event.market_id == "0xws1"
        assert event.channel == WebSocketChannel.USER_FILL
        assert event.event_type == "fill"
        assert event.data["size"] == "100.0"

    def test_market_event_channel_enum_values(self) -> None:
        """All WebSocketChannel members are accessible."""
        assert WebSocketChannel.USER_FILL.value == WebSocketChannel.USER_FILL.value
        assert WebSocketChannel.BOOK in WebSocketChannel
        assert WebSocketChannel.TICKER in WebSocketChannel
        assert WebSocketChannel.LAST_TRADE_PRICE in WebSocketChannel
        assert WebSocketChannel.USER_ORDER in WebSocketChannel

    @pytest.mark.asyncio
    async def test_market_event_async_generator(self) -> None:
        """An async generator yielding MarketEvent works with async for."""
        events = [
            MarketEvent(
                market_id="0xgen1",
                channel=WebSocketChannel.USER_FILL,
                event_type="fill",
                data={"size": "10.0", "price": "0.50", "side": "BUY"},
                timestamp=datetime(2026, 6, 1, 12, 0, 0),
            ),
            MarketEvent(
                market_id="0xgen2",
                channel=WebSocketChannel.BOOK,
                event_type="book_update",
                data={"bid": "0.49", "ask": "0.51"},
                timestamp=datetime(2026, 6, 1, 12, 0, 1),
            ),
        ]

        seen: list[MarketEvent] = []
        async for event in _event_stream(events):
            seen.append(event)

        assert len(seen) == 2
        assert seen[0].market_id == "0xgen1"
        assert seen[1].market_id == "0xgen2"

    @pytest.mark.asyncio
    async def test_websocket_adapter_config_and_connect_fails_no_server(self) -> None:
        """A WebSocket adapter configured with a bogus URL fails to connect."""
        config = WebSocketConfig(
            url="ws://localhost:19831/nonexistent",
            channels=[WebSocketChannel.USER_FILL],
            reconnect_delay=0.1,
            max_reconnects=1,
        )
        adapter = PolymarketWebSocketAdapter(config)
        with pytest.raises((ConnectionRefusedError, OSError, TimeoutError)):
            await adapter.connect()
        assert not adapter.connected

    def test_websocket_config_defaults(self) -> None:
        """WebSocketConfig provides sensible defaults."""
        config = WebSocketConfig(url="wss://example.com/ws")
        assert config.channels == []
        assert config.auth_token is None
        assert config.reconnect_delay == 1.0
        assert config.max_reconnects == 5

    @pytest.mark.asyncio
    async def test_fill_reconciler_cross_check_with_market_event(self) -> None:
        """FillReconciler.cross_check_fills matches WebSocket fills against CLOB fills.

        MarketEvent data is converted to FillEvents; cross_check_fills
        detects discrepancies between the two sources.
        """
        reconciler = FillReconciler()

        # Simulate fills from two sources
        ws_fills = [
            FillEvent(
                fill_id="fill-001",
                market_id="0xcross",
                outcome="YES",
                side=OrderSide.BUY,
                price=0.50,
                size=100.0,
                fee=0.0,
                timestamp=datetime(2026, 6, 1, 12, 0, 0),
                source=FillSource.WEBSOCKET,
            ),
            FillEvent(
                fill_id="fill-002",
                market_id="0xcross",
                outcome="YES",
                side=OrderSide.BUY,
                price=0.51,
                size=50.0,
                fee=0.0,
                timestamp=datetime(2026, 6, 1, 12, 0, 1),
                source=FillSource.WEBSOCKET,
            ),
        ]
        clob_fills = [
            FillEvent(
                fill_id="fill-001",
                market_id="0xcross",
                outcome="YES",
                side=OrderSide.BUY,
                price=0.50,
                size=100.0,
                fee=0.0,
                timestamp=datetime(2026, 6, 1, 12, 0, 0),
                source=FillSource.CLOB_API,
            ),
            # fill-002 is missing from CLOB
        ]

        records = reconciler.cross_check_fills(ws_fills, clob_fills)
        assert len(records) == 2

        # fill-001 should be matched
        matched = [r for r in records if r.identity_string == "fill-001"]
        assert len(matched) == 1
        assert matched[0].status == ReconciliationStatus.MATCHED

        # fill-002 should be unexpected (missing from CLOB)
        unexpected = [r for r in records if r.identity_string == "fill-002"]
        assert len(unexpected) == 1
        assert unexpected[0].status == ReconciliationStatus.UNEXPECTED

    @pytest.mark.asyncio
    async def test_fill_reconciler_detects_mismatch(self) -> None:
        """FillReconciler reports MISMATCHED when size or price differs."""
        reconciler = FillReconciler()

        ws_fills = [
            FillEvent(
                fill_id="fill-003",
                market_id="0xmm",
                outcome="YES",
                side=OrderSide.BUY,
                price=0.50,
                size=100.0,
                fee=0.0,
                timestamp=datetime(2026, 6, 1, 12, 0, 0),
                source=FillSource.WEBSOCKET,
            ),
        ]
        clob_fills = [
            FillEvent(
                fill_id="fill-003",
                market_id="0xmm",
                outcome="YES",
                side=OrderSide.BUY,
                price=0.52,  # Different price
                size=95.0,  # Different size
                fee=0.0,
                timestamp=datetime(2026, 6, 1, 12, 0, 0),
                source=FillSource.CLOB_API,
            ),
        ]

        records = reconciler.cross_check_fills(ws_fills, clob_fills)
        mismatched = [r for r in records if r.status == ReconciliationStatus.MISMATCHED]
        assert len(mismatched) == 1

    @pytest.mark.asyncio
    async def test_convert_market_event_to_fill_event(self) -> None:
        """A USER_FILL MarketEvent can be converted to a FillEvent for reconciliation."""
        market_event = MarketEvent(
            market_id="0xconvert",
            channel=WebSocketChannel.USER_FILL,
            event_type="fill",
            data={
                "id": "fill-convert-001",
                "market": "0xconvert",
                "outcome": "YES",
                "side": "BUY",
                "price": "0.50",
                "size": "100.0",
                "fee": "0.001",
                "timestamp": "2026-06-01T12:00:00Z",
            },
            timestamp=datetime(2026, 6, 1, 12, 0, 0),
        )

        fill = _market_event_to_fill(market_event)
        assert fill.fill_id == "fill-convert-001"
        assert fill.market_id == "0xconvert"
        assert fill.side == OrderSide.BUY
        assert abs(fill.price - 0.50) < 0.0001
        assert abs(fill.size - 100.0) < 0.0001
        assert fill.source == FillSource.WEBSOCKET


# ─────────────────────────────────────────────────────────────────────────────
# Helper utilities
# ─────────────────────────────────────────────────────────────────────────────


class _SafeExecutorGuard:
    """Wrapper around an IntentExecutor that checks KillSwitch before execution.

    This demonstrates the integration pattern: a guard that refuses to execute
    orders once the kill switch is triggered.
    """

    def __init__(self, executor: IntentExecutor, kill_switch: KillSwitch) -> None:
        self._executor = executor
        self._kill_switch = kill_switch

    async def execute(self, intent: StrategyIntent) -> dict[str, Any]:
        if self._kill_switch.is_triggered():
            return {}
        return await self._executor.execute(intent)

    async def dry_run(self, intent: StrategyIntent) -> dict[str, Any]:
        if self._kill_switch.is_triggered():
            return {}
        return await self._executor.dry_run(intent)


class _StubContractsGateway:
    """Minimal stub that returns pre-configured balances for BalanceReconciler."""

    def __init__(self, balances: dict[str, float]) -> None:
        self._balances = balances
        self._closed = False

    async def balance_of(self, owner: str, token_id: str) -> float:
        return self._balances.get(token_id, 0.0)

    async def close(self) -> None:
        self._closed = True


async def _event_stream(events: list[MarketEvent]):
    """Simple async generator yielding MarketEvent objects."""
    for event in events:
        yield event


def _make_fill(market_id: str, fill_id: str, size: float, price: float) -> FillEvent:
    """Convenience factory for FillEvent fixtures."""
    return FillEvent(
        fill_id=fill_id,
        market_id=market_id,
        outcome="YES",
        side=OrderSide.BUY,
        price=price,
        size=size,
        fee=0.0,
        timestamp=datetime(2026, 1, 1),
        source=FillSource.SIMULATED,
    )


def _market_event_to_fill(event: MarketEvent) -> FillEvent:
    """Convert a USER_FILL MarketEvent into a FillEvent.

    This is a simplified conversion — a production implementation would
    handle field name variations, type coercion, and error handling.
    """
    d = event.data
    side_str = d.get("side", "BUY").upper()
    side = OrderSide.BUY if side_str == "BUY" else OrderSide.SELL

    return FillEvent(
        fill_id=d.get("id", ""),
        market_id=d.get("market", event.market_id),
        outcome=d.get("outcome", "YES"),
        side=side,
        price=float(d.get("price", 0.0)),
        size=float(d.get("size", 0.0)),
        fee=float(d.get("fee", 0.0)),
        timestamp=event.timestamp,
        source=FillSource.WEBSOCKET,
    )
