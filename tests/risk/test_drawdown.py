"""Tests for DrawdownTracker."""

from __future__ import annotations

import pytest

from polymind.risk.drawdown import DrawdownConfig, DrawdownState, DrawdownTracker


class TestDrawdownState:
    def test_enum_values(self):
        assert isinstance(DrawdownState.NORMAL, DrawdownState)
        assert isinstance(DrawdownState.WARNING, DrawdownState)
        assert isinstance(DrawdownState.STOPPED, DrawdownState)
        assert isinstance(DrawdownState.RECOVERY, DrawdownState)


class TestDrawdownConfig:
    def test_defaults(self):
        c = DrawdownConfig()
        assert c.max_drawdown_pct == 0.15
        assert c.warning_pct == 0.10
        assert c.recovery_pct == 0.05

    def test_custom_values(self):
        c = DrawdownConfig(max_drawdown_pct=0.20, warning_pct=0.12, recovery_pct=0.03)
        assert c.max_drawdown_pct == 0.20
        assert c.warning_pct == 0.12
        assert c.recovery_pct == 0.03


class TestDrawdownTracker:
    def test_init_with_initial_peak(self):
        t = DrawdownTracker(DrawdownConfig(), initial_peak=50_000.0)
        assert t.get_peak() == 50_000.0
        assert t.get_state() is DrawdownState.NORMAL

    def test_update_with_gain_increases_peak(self):
        t = DrawdownTracker(DrawdownConfig(), initial_peak=100.0)
        state = t.update(120.0)
        assert t.get_peak() == 120.0
        assert state is DrawdownState.NORMAL

    def test_small_loss_stays_normal(self):
        t = DrawdownTracker(DrawdownConfig(), initial_peak=100.0)
        state = t.update(95.0)
        assert state is DrawdownState.NORMAL

    def test_loss_above_warning_goes_warning(self):
        t = DrawdownTracker(DrawdownConfig(), initial_peak=100.0)
        state = t.update(88.0)
        assert state is DrawdownState.WARNING

    def test_loss_above_max_drawdown_goes_stopped(self):
        t = DrawdownTracker(DrawdownConfig(), initial_peak=100.0)
        state = t.update(84.0)
        assert state is DrawdownState.STOPPED

    def test_recovery_after_stopped_goes_recovery(self):
        config = DrawdownConfig(max_drawdown_pct=0.15, warning_pct=0.10, recovery_pct=0.05)
        t = DrawdownTracker(config, initial_peak=100.0)
        t.update(84.0)  # -> STOPPED
        state = t.update(96.0)  # drawdown ~4%, below recovery_pct -> RECOVERY
        assert state is DrawdownState.RECOVERY

    def test_get_drawdown_pct(self):
        t = DrawdownTracker(DrawdownConfig(), initial_peak=100.0)
        t.update(90.0)
        assert t.get_drawdown_pct() == pytest.approx(0.10)

    def test_get_peak(self):
        t = DrawdownTracker(DrawdownConfig(), initial_peak=100.0)
        t.update(110.0)
        t.update(105.0)
        assert t.get_peak() == 110.0

    def test_reset_changes_peak(self):
        t = DrawdownTracker(DrawdownConfig(), initial_peak=100.0)
        t.update(80.0)
        assert t.get_state() is DrawdownState.STOPPED
        t.reset(200.0)
        assert t.get_peak() == 200.0
        assert t.get_state() is DrawdownState.NORMAL
