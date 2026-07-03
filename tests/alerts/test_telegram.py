"""
Tests for AlertManager.
"""

from __future__ import annotations

from polymind.alerts.telegram import AlertManager


class TestAlertManager:
    def test_info(self):
        m = AlertManager()
        m.info("test message")
        assert m.get_unread_count() == 1

    def test_levels(self):
        m = AlertManager()
        m.info("i")
        m.warn("w")
        m.error("e")
        m.critical("c")
        assert m.get_unread_count() == 4

    def test_clear(self):
        m = AlertManager()
        m.info("x")
        m.clear()
        assert m.get_unread_count() == 0

    def test_get_recent(self):
        m = AlertManager()
        for i in range(5):
            m.info(f"msg {i}")
        recent = m.get_recent(3)
        assert len(recent) == 3
