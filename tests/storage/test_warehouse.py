"""
Tests for DataWarehouse.
"""

from __future__ import annotations

from datetime import datetime

from polymind.storage.warehouse import DataWarehouse, MarketMetadata, MarketPanel


class TestMarketPanel:
    def test_empty(self):
        p = MarketPanel(market_id="0xabc")
        assert len(p.timestamps) == 0


class TestMarketMetadata:
    def test_defaults(self):
        m = MarketMetadata(market_id="0xabc")
        assert m.outcome_a == "YES"
        assert m.fee_rate == 0.003


class TestDataWarehouse:
    def test_register_and_list(self):
        dw = DataWarehouse()
        dw.register_market(MarketMetadata(market_id="0xabc"))
        assert "0xabc" in dw.list_markets()

    def test_append_snapshot(self):
        dw = DataWarehouse()
        now = datetime.now()
        dw.append_snapshot("0xabc", now, 0.50, 0.48, 0.52, 10000.0)
        panel = dw.get_panel("0xabc")
        assert panel is not None
        assert len(panel.timestamps) == 1
        assert panel.mid_prices[0] == 0.50

    def test_latest_prices(self):
        dw = DataWarehouse()
        now = datetime.now()
        dw.append_snapshot("0xabc", now, 0.50)
        dw.append_snapshot("0xabc", datetime.now(), 0.55)
        dw.append_snapshot("0xdef", datetime.now(), 0.30)
        prices = dw.latest_prices()
        assert prices["0xabc"] == 0.55
        assert prices["0xdef"] == 0.30

    def test_spread_calculation(self):
        dw = DataWarehouse()
        dw.append_snapshot("0xabc", datetime.now(), 0.50, 0.498, 0.502)
        panel = dw.get_panel("0xabc")
        # spread = (0.502 - 0.498) / 0.50 * 10000 = 80 bps
        assert abs(panel.spreads_bps[0] - 80.0) < 1.0

    def test_get_metadata(self):
        dw = DataWarehouse()
        meta = MarketMetadata(market_id="0xabc", question="Will X happen?")
        dw.register_market(meta)
        retrieved = dw.get_metadata("0xabc")
        assert retrieved is not None
        assert retrieved.question == "Will X happen?"
