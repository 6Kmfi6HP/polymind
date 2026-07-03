"""
Safety Features Example — kill switch, drawdown, preflight, limits.

Demonstrates:
1. KillSwitch trigger/release mechanism
2. PreflightChecker configuration validation
3. DrawdownTracker state machine
4. LimitsManager position/order/exposure limits

Run: python3 examples/safety_example.py
"""

from __future__ import annotations

import os
import asyncio

from polymind.risk.drawdown import DrawdownConfig, DrawdownTracker
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


async def main() -> None:
    print("=" * 60)
    print("Safety Features Example")
    print("=" * 60)

    # 1. KillSwitch
    print("\n--- KillSwitch ---")
    ks = KillSwitch(file_path="/tmp/_polymind_kill_test")
    print(f"Default state (should be False): {ks.is_triggered()}")

    ks.trigger()
    print(f"After trigger (should be True): {ks.is_triggered()}")

    ks.release()
    print(f"After release (should be False): {ks.is_triggered()}")

    # Cleanup
    if os.path.exists("/tmp/_polymind_kill_test"):
        os.remove("/tmp/_polymind_kill_test")

    # 2. Preflight
    print("\n--- Preflight Checks ---")
    checker = PreflightChecker()

    config_check = checker.check_config(
        {"api_key": "sk-123", "host": "localhost"},
        required_keys=["api_key", "private_key"],
    )
    print(f"Config check (missing private_key): passed={config_check.passed}")

    cred_check = checker.check_credentials(has_api_key=True, has_private_key=False)
    print(f"Credential check (missing wallet): severity={cred_check.severity.name}")

    # 3. DrawdownTracker
    print("\n--- Drawdown Protection ---")
    tracker = DrawdownTracker(
        DrawdownConfig(max_drawdown_pct=0.15, warning_pct=0.10, recovery_pct=0.05),
        initial_peak=10_000.0,
    )
    print(f"Initial state: {tracker.get_state().name}, peak=${tracker.get_peak():.0f}")

    tracker.update(9_200.0)
    print(f"After -8%: state={tracker.get_state().name}, dd={tracker.get_drawdown_pct():.1%}")

    tracker.update(8_500.0)
    print(f"After -15%: state={tracker.get_state().name}, dd={tracker.get_drawdown_pct():.1%}")

    tracker.update(8_000.0)
    print(f"After -20%: state={tracker.get_state().name}, dd={tracker.get_drawdown_pct():.1%}")

    # 4. LimitsManager
    print("\n--- Position Limits ---")
    config = LimitsConfig(
        positions=[PositionLimit(market_id="0xabc", max_size=500.0, max_notional=250.0, min_size=1.0)],
        order_rate=OrderRateLimit(max_orders_per_window=10, window_seconds=60),
        daily_loss=DailyLossLimit(max_loss_amount=500.0, max_loss_pct=0.05),
        exposure=ExposureLimit(max_total_exposure=2000.0, max_per_market_pct=0.25),
    )
    lm = LimitsManager(config)
    print(f"Size 100.0 within limit: {lm.check_position_size('0xabc', 100.0)}")
    print(f"Size 9999.0 exceeds limit: {not lm.check_position_size('0xabc', 9999.0)}")
    print(f"Order rate 5 within limit: {lm.check_order_rate(5)}")
    print(f"Order rate 15 exceeds limit: {not lm.check_order_rate(15)}")

    # Combined check
    print(f"\nAll checks pass: {lm.check_all('0xabc', 100.0, 5, 500.0, 1000.0)}")
    print(f"All checks fail: {lm.check_all('0xabc', 9999.0, 15, 5000.0, 5000.0)}")

    print("\n✅ Safety features example completed successfully!")


if __name__ == "__main__":
    asyncio.run(main())
