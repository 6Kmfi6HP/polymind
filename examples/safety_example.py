"""
Safety Features Example — KillSwitch, PreflightChecker, DrawdownTracker, LimitsManager.

Demonstrates:
1. KillSwitch  — emergency stop via sentinel file or in-memory flag
2. PreflightChecker  — config/credential validation before deployment
3. DrawdownTracker  — state machine that monitors drawdown from peak equity
4. LimitsManager  — position size, order rate, daily loss, and exposure limits

Run: python3 examples/safety_example.py
"""

from __future__ import annotations

import os

from polymind.risk.drawdown import DrawdownConfig, DrawdownState, DrawdownTracker
from polymind.risk.limits import (
    DailyLossLimit,
    ExposureLimit,
    LimitsConfig,
    LimitsManager,
    OrderRateLimit,
    PositionLimit,
)
from polymind.utils.killswitch import KillSwitch
from polymind.utils.preflight import PreflightChecker


def demo_killswitch() -> None:
    """KillSwitch — in-memory flag variant (no sentinel file needed).

    A KillSwitch acts as a circuit breaker: once triggered, any trading loop
    can poll ``is_triggered()`` and halt immediately.  The file-based variant
    (pass ``file_path=``) is useful for cross-process signalling — creating
    the file kills all running instances.
    """
    print("=" * 72)
    print("1. KillSwitch — Emergency Stop")
    print("=" * 72)

    # In-memory flag mode: no sentinel file on disk
    ks = KillSwitch()

    print("    is_triggered() →", ks.is_triggered(), "(expect False)")
    assert not ks.is_triggered(), "KillSwitch should start released"

    ks.trigger()
    print("    after trigger() →", ks.is_triggered(), "(expect True)")
    assert ks.is_triggered(), "KillSwitch should report True after trigger"

    ks.release()
    print("    after release() →", ks.is_triggered(), "(expect False)")
    assert not ks.is_triggered(), "KillSwitch should return to False after release"

    # File-based variant (creates/removes a sentinel file on disk)
    sentinel = "/tmp/_polymind_kill_test"
    ks_file = KillSwitch(file_path=sentinel)
    print("\n    [file-based] is_triggered() →", ks_file.is_triggered(), "(expect False)")

    ks_file.trigger()
    print("    [file-based] after trigger() →", ks_file.is_triggered(), "(expect True)")
    assert os.path.exists(sentinel), "Sentinel file should exist on disk"

    ks_file.release()
    print("    [file-based] after release() →", ks_file.is_triggered(), "(expect False)")
    assert not os.path.exists(sentinel), "Sentinel file should be removed"

    print("  ✅ KillSwitch OK\n")


def demo_preflight() -> None:
    """PreflightChecker — validate config and credentials before trading starts.

    Use ``PreflightChecker`` in your deployment script or strategy initialiser
    to fail fast when required keys or credentials are missing, rather than
    crashing mid-trade.
    """
    print("=" * 72)
    print("2. PreflightChecker — Pre-deployment Validation")
    print("=" * 72)

    # --- Scenario A: valid config, all credentials present ---
    valid_config = {
        "platform": "polymarket",
        "initial_capital": 10_000.0,
        "api_key": "sk-abc123",
        "private_key": "0xdeadbeef",
    }
    report = PreflightChecker.run_all(
        valid_config,
        has_api_key=True,
        has_private_key=True,
    )
    print("    valid config + credentials → passed =", report.passed, "(expect True)")
    assert report.passed
    for r in report.results:
        print(f"      [{r.severity.name:5s}] {r.check_name}: {r.message}")

    # --- Scenario B: missing config keys, no private key ---
    bad_config = {
        "api_key": "sk-abc123",
        # missing "platform" and "initial_capital"
    }
    report = PreflightChecker.run_all(
        bad_config,
        has_api_key=True,
        has_private_key=False,
    )
    print("\n    bad config + missing wallet → passed =", report.passed, "(expect False)")
    assert not report.passed
    for r in report.results:
        print(f"      [{r.severity.name:5s}] {r.check_name}: {r.message}")

    # --- Individual check example ---
    result = PreflightChecker.check_config(
        {"host": "localhost"},
        required_keys=["host", "port", "timeout"],
    )
    print("\n    custom check (host only; need host+port+timeout):")
    print(f"      passed = {result.passed}  →  {result.message}")

    print("  ✅ PreflightChecker OK\n")


def demo_drawdown() -> None:
    """DrawdownTracker — state machine protecting against peak-to-trough losses.

    States (``DrawdownState``):

        NORMAL    — drawdown < warning_pct
        WARNING   — warning_pct ≤ drawdown < max_drawdown_pct
        STOPPED   — drawdown ≥ max_drawdown_pct   (trading should halt)
        RECOVERY  — was STOPPED, now recovered below recovery_pct

    When a new peak is reached the tracker resets to NORMAL automatically.
    """
    print("=" * 72)
    print("3. DrawdownTracker — Peak-to-Trough State Machine")
    print("=" * 72)

    # Thresholds: warn at 10%, halt at 15%, consider recovery at ≤5%
    config = DrawdownConfig(
        max_drawdown_pct=0.15,
        warning_pct=0.10,
        recovery_pct=0.05,
    )
    tracker = DrawdownTracker(config, initial_peak=10_000.0)

    # Snapshot of starting state
    print(
        f"\n    Start:        equity=$10 000  "
        f"state={tracker.get_state().name:8s}  "
        f"dd={tracker.get_drawdown_pct():.1%}"
    )

    # Move 1: small dip — should stay NORMAL
    tracker.update(9_400.0)
    print(
        f"    -6% dip:      equity=$9 400  "
        f"state={tracker.get_state().name:8s}  "
        f"dd={tracker.get_drawdown_pct():.1%}"
    )
    assert tracker.get_state() == DrawdownState.NORMAL, "6% dip should be NORMAL"

    # Move 2: deeper — crosses warning_pct (10%)
    tracker.update(8_900.0)
    print(
        f"    -11% drop:    equity=$8 900  "
        f"state={tracker.get_state().name:8s}  "
        f"dd={tracker.get_drawdown_pct():.1%}"
    )
    assert tracker.get_state() == DrawdownState.WARNING, "11% drop should be WARNING"

    # Move 3: plunges past max_drawdown_pct (15%)
    tracker.update(8_400.0)
    print(
        f"    -16% plunge:  equity=$8 400  "
        f"state={tracker.get_state().name:8s}  "
        f"dd={tracker.get_drawdown_pct():.1%}"
    )
    assert tracker.get_state() == DrawdownState.STOPPED, "16% drop should be STOPPED"

    # Move 4: partial bounce, still above max_drawdown_pct (15%) → stays STOPPED
    tracker.update(8_450.0)
    print(
        f"    +0.6% bounce: equity=$8 450  "
        f"state={tracker.get_state().name:8s}  "
        f"dd={tracker.get_drawdown_pct():.1%}"
    )
    assert tracker.get_state() == DrawdownState.STOPPED, "15.5% down → STOPPED"

    # Move 5: new peak → auto-resets to NORMAL, peak moves up
    tracker.update(10_500.0)
    print(
        f"    new peak:     equity=$10 500 "
        f"state={tracker.get_state().name:8s}  "
        f"dd={tracker.get_drawdown_pct():.1%}"
    )
    assert tracker.get_state() == DrawdownState.NORMAL, "New peak should be NORMAL"
    assert tracker.get_peak() == 10_500.0, "Peak should have updated"

    # Move 6: severe drawdown past STOPPED, then recovery below recovery_pct
    tracker.update(8_000.0)  # dd = (10_500-8_000)/10_500 ≈ 23.8% → STOPPED
    print(
        f"    -24% crash:   equity=$8 000  "
        f"state={tracker.get_state().name:8s}  "
        f"dd={tracker.get_drawdown_pct():.1%}"
    )
    assert tracker.get_state() == DrawdownState.STOPPED

    tracker.update(10_100.0)  # dd ≈ 3.8% ≤ recovery_pct → RECOVERY
    print(
        f"    recovers:     equity=$10 100 "
        f"state={tracker.get_state().name:8s}  "
        f"dd={tracker.get_drawdown_pct():.1%}"
    )
    assert tracker.get_state() == DrawdownState.RECOVERY, "Should be RECOVERY"

    print("  ✅ DrawdownTracker OK\n")


def demo_limits() -> None:
    """LimitsManager — enforce position size, order rate, daily loss, exposure.

    Each limit type can be configured independently.  The ``check_all()``
    shortcut runs all checks at once and returns a list of failure reasons
    (empty list = all passed).
    """
    print("=" * 72)
    print("4. LimitsManager — Position, Rate, Loss & Exposure Limits")
    print("=" * 72)

    config = LimitsConfig(
        positions=[
            PositionLimit(
                market_id="0xabc",
                max_size=500.0,
                max_notional=250.0,
                min_size=1.0,
            ),
        ],
        order_rate=OrderRateLimit(max_orders_per_window=10, window_seconds=60),
        daily_loss=DailyLossLimit(max_loss_amount=500.0, max_loss_pct=5.0),
        exposure=ExposureLimit(
            max_total_exposure=2000.0,
            max_per_market_pct=25.0,  # 25% of total in a single market
        ),
    )
    lm = LimitsManager(config)

    # --- Individual checks ---
    print("\n  Position size checks (market=0xabc, min=1.0, max=500.0):")
    for size, expected in [(100.0, True), (0.5, False), (500.0, True), (600.0, False)]:
        actual = lm.check_position_size("0xabc", size)
        status = "OK" if actual == expected else "FAIL"
        print(f"    size={size:<6} → {actual}  (expect {expected})  [{status}]")
        assert actual == expected, f"Position size {size}: expected {expected}, got {actual}"

    print("\n  Order rate checks (max 10 / 60s window):")
    for count, expected in [(5, True), (10, True), (11, False)]:
        actual = lm.check_order_rate(count)
        status = "OK" if actual == expected else "FAIL"
        print(f"    orders={count:<2} → {actual}  (expect {expected})  [{status}]")
        assert actual == expected, f"Order count {count}: expected {expected}, got {actual}"

    print("\n  Daily loss checks (max_loss=500):")
    # PnL is the new trade result; additional_loss = max(0, -pnl)
    for current_loss, pnl, expected in [
        (100.0, -50.0, True),  # total loss = 150, within limit
        (0.0, -500.0, True),  # total loss = 500, exactly at limit
        (0.0, -500.01, False),  # total loss = 500.01, exceeded
    ]:
        actual = lm.check_daily_loss(current_loss, pnl)
        status = "OK" if actual == expected else "FAIL"
        print(
            f"    loss={current_loss:<4} pnl={pnl:<6} → {actual}  (expect {expected})  [{status}]"
        )
        assert actual == expected, f"Loss {current_loss} pnl {pnl}: expected {expected}"

    print("\n  Exposure checks (max total=2000, max per-market=25%):")
    for current, new, expected in [
        (0.0, 500.0, True),  # 500 ≤ 2000,  25% ≤ 25%
        (0.0, 501.0, False),  # 25.05% > 25%
        (1_800.0, 300.0, False),  # 2100 > 2000
    ]:
        actual = lm.check_exposure(current, new)
        status = "OK" if actual == expected else "FAIL"
        print(f"    cur={current:<5} new={new:<5} → {actual}  (expect {expected})  [{status}]")
        assert actual == expected, f"Exposure cur={current} new={new}: expected {expected}"

    # --- Combined check_all ---
    print("\n  Combined check_all (one call = all checks at once):")
    failures = lm.check_all("0xabc", 100.0, 5, 200.0, 200.0)
    print(f"    all compliant                → {failures}  (expect [])")
    assert failures == [], f"Expected no failures, got {failures}"

    failures = lm.check_all("0xabc", 9999.0, 15, 1000.0, 5000.0)
    print(f"    all violating                → {failures}")
    assert len(failures) == 4, "Expected 4 violations"

    print("  ✅ LimitsManager OK\n")


def main() -> None:
    print()
    demo_killswitch()
    demo_preflight()
    demo_drawdown()
    demo_limits()

    print("=" * 72)
    print("All safety features verified successfully.")
    print("=" * 72)


if __name__ == "__main__":
    main()
