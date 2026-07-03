"""Tests for storage domain models (OrderModel, FillModel, PositionModel)."""

from __future__ import annotations

from datetime import datetime

import pytest

from polymind.storage.models import DBModel, FillModel, OrderModel, PositionModel


class TestOrderModel:
    """Construction, serialisation, and DDL for OrderModel."""

    def test_construction(self):
        now = datetime.now()
        order = OrderModel(
            order_id="ord-1",
            market_id="0xabc",
            token_id="12345",
            side="BUY",
            price=0.85,
            size=100.0,
            status="OPEN",
            created_at=now,
            updated_at=now,
        )
        assert order.order_id == "ord-1"
        assert order.market_id == "0xabc"
        assert order.token_id == "12345"
        assert order.side == "BUY"
        assert order.price == 0.85
        assert order.size == 100.0
        assert order.status == "OPEN"
        assert order.created_at == now
        assert order.updated_at == now

    def test_tablename(self):
        assert OrderModel.tablename() == "orders"

    def test_to_dict(self):
        now = datetime(2026, 7, 3, 12, 0, 0)
        order = OrderModel(
            order_id="ord-1",
            market_id="0xabc",
            token_id="12345",
            side="BUY",
            price=0.85,
            size=100.0,
            status="OPEN",
            created_at=now,
            updated_at=now,
        )
        d = order.to_dict()
        assert d["order_id"] == "ord-1"
        assert d["created_at"] == "2026-07-03T12:00:00"
        assert d["updated_at"] == "2026-07-03T12:00:00"

    def test_from_dict(self):
        data = {
            "order_id": "ord-1",
            "market_id": "0xabc",
            "token_id": "12345",
            "side": "BUY",
            "price": 0.85,
            "size": 100.0,
            "status": "OPEN",
            "created_at": "2026-07-03T12:00:00",
            "updated_at": "2026-07-03T12:00:00",
        }
        order = OrderModel.from_dict(data)
        assert order.order_id == "ord-1"
        assert order.price == 0.85
        assert order.created_at == datetime(2026, 7, 3, 12, 0, 0)

    def test_to_dict_from_dict_round_trip(self):
        now = datetime.now()
        original = OrderModel(
            order_id="ord-2",
            market_id="0xdef",
            token_id="67890",
            side="SELL",
            price=0.42,
            size=50.0,
            status="FILLED",
            created_at=now,
            updated_at=now,
        )
        restored = OrderModel.from_dict(original.to_dict())
        assert restored == original
        assert restored.created_at == original.created_at
        assert restored.updated_at == original.updated_at

    def test_create_table_sql(self):
        sql = OrderModel.create_table_sql()
        assert sql.startswith("CREATE TABLE IF NOT EXISTS")
        assert "order_id" in sql
        assert "PRIMARY KEY" in sql

    def test_schema_is_valid_sql(self):
        """The SCHEMA constant should parse without error when executed."""
        import sqlite3

        conn = sqlite3.connect(":memory:")
        try:
            conn.execute(OrderModel.SCHEMA)
            cols = {row[1] for row in conn.execute("PRAGMA table_info(orders)").fetchall()}
            assert "order_id" in cols
            assert "market_id" in cols
            assert "token_id" in cols
            assert "side" in cols
            assert "price" in cols
            assert "size" in cols
            assert "status" in cols
            assert "created_at" in cols
            assert "updated_at" in cols
        finally:
            conn.close()


class TestFillModel:
    """Construction, serialisation, and DDL for FillModel."""

    def test_construction(self):
        ts = datetime.now()
        fill = FillModel(
            fill_id="fill-1",
            order_id="ord-1",
            market_id="0xabc",
            side="BUY",
            price=0.85,
            size=10.0,
            fee=0.0255,
            timestamp=ts,
        )
        assert fill.fill_id == "fill-1"
        assert fill.order_id == "ord-1"
        assert fill.market_id == "0xabc"
        assert fill.side == "BUY"
        assert fill.price == 0.85
        assert fill.size == 10.0
        assert fill.fee == 0.0255
        assert fill.timestamp == ts

    def test_tablename(self):
        assert FillModel.tablename() == "fills"

    def test_to_dict(self):
        ts = datetime(2026, 7, 3, 12, 34, 56)
        fill = FillModel(
            fill_id="fill-1",
            order_id="ord-1",
            market_id="0xabc",
            side="SELL",
            price=0.75,
            size=5.0,
            fee=0.01125,
            timestamp=ts,
        )
        d = fill.to_dict()
        assert d["fill_id"] == "fill-1"
        assert d["timestamp"] == "2026-07-03T12:34:56"

    def test_from_dict(self):
        data = {
            "fill_id": "fill-1",
            "order_id": "ord-1",
            "market_id": "0xabc",
            "side": "SELL",
            "price": 0.75,
            "size": 5.0,
            "fee": 0.01125,
            "timestamp": "2026-07-03T12:34:56",
        }
        fill = FillModel.from_dict(data)
        assert fill.fill_id == "fill-1"
        assert fill.price == 0.75
        assert fill.timestamp == datetime(2026, 7, 3, 12, 34, 56)

    def test_to_dict_from_dict_round_trip(self):
        ts = datetime.now()
        original = FillModel(
            fill_id="fill-2",
            order_id="ord-2",
            market_id="0xdef",
            side="BUY",
            price=0.90,
            size=20.0,
            fee=0.0,
            timestamp=ts,
        )
        restored = FillModel.from_dict(original.to_dict())
        assert restored == original
        assert restored.timestamp == original.timestamp

    def test_create_table_sql(self):
        sql = FillModel.create_table_sql()
        assert sql.startswith("CREATE TABLE IF NOT EXISTS")
        assert "fill_id" in sql
        assert "PRIMARY KEY" in sql

    def test_schema_is_valid_sql(self):
        import sqlite3

        conn = sqlite3.connect(":memory:")
        try:
            conn.execute(FillModel.SCHEMA)
            cols = {row[1] for row in conn.execute("PRAGMA table_info(fills)").fetchall()}
            assert "fill_id" in cols
            assert "order_id" in cols
            assert "price" in cols
            assert "fee" in cols
        finally:
            conn.close()


class TestPositionModel:
    """Construction, serialisation, and DDL for PositionModel."""

    def test_construction(self):
        now = datetime.now()
        pos = PositionModel(
            market_id="0xabc",
            token_id="12345",
            size=50.0,
            avg_entry=0.80,
            realized_pnl=12.50,
            updated_at=now,
        )
        assert pos.market_id == "0xabc"
        assert pos.token_id == "12345"
        assert pos.size == 50.0
        assert pos.avg_entry == 0.80
        assert pos.realized_pnl == 12.50
        assert pos.updated_at == now

    def test_tablename(self):
        assert PositionModel.tablename() == "positions"

    def test_to_dict(self):
        now = datetime(2026, 7, 3, 15, 0, 0)
        pos = PositionModel(
            market_id="0xabc",
            token_id="12345",
            size=50.0,
            avg_entry=0.80,
            realized_pnl=12.50,
            updated_at=now,
        )
        d = pos.to_dict()
        assert d["market_id"] == "0xabc"
        assert d["updated_at"] == "2026-07-03T15:00:00"

    def test_from_dict(self):
        data = {
            "market_id": "0xabc",
            "token_id": "12345",
            "size": 50.0,
            "avg_entry": 0.80,
            "realized_pnl": 12.50,
            "updated_at": "2026-07-03T15:00:00",
        }
        pos = PositionModel.from_dict(data)
        assert pos.market_id == "0xabc"
        assert pos.avg_entry == 0.80
        assert pos.updated_at == datetime(2026, 7, 3, 15, 0, 0)

    def test_to_dict_from_dict_round_trip(self):
        now = datetime.now()
        original = PositionModel(
            market_id="0xdef",
            token_id="67890",
            size=-10.0,
            avg_entry=0.65,
            realized_pnl=-2.00,
            updated_at=now,
        )
        restored = PositionModel.from_dict(original.to_dict())
        assert restored == original
        assert restored.updated_at == original.updated_at

    def test_create_table_sql(self):
        sql = PositionModel.create_table_sql()
        assert sql.startswith("CREATE TABLE IF NOT EXISTS")
        assert "PRIMARY KEY" in sql
        assert "market_id" in sql
        assert "token_id" in sql

    def test_schema_is_valid_sql(self):
        import sqlite3

        conn = sqlite3.connect(":memory:")
        try:
            conn.execute(PositionModel.SCHEMA)
            cols = {row[1] for row in conn.execute("PRAGMA table_info(positions)").fetchall()}
            assert "market_id" in cols
            assert "token_id" in cols
            assert "size" in cols
            assert "avg_entry" in cols
            assert "realized_pnl" in cols
            assert "updated_at" in cols
        finally:
            conn.close()


class TestDBModelBase:
    """Tests for the DBModel ABC."""

    def test_cannot_instantiate_abc(self):
        with pytest.raises(TypeError):
            DBModel()  # type: ignore[abstract]

    def test_all_concrete_models_have_schema(self):
        for cls in (OrderModel, FillModel, PositionModel):
            assert cls.SCHEMA, f"{cls.__name__}.SCHEMA should not be empty"

    def test_create_table_sql_uses_schema(self):
        """create_table_sql() delegates to SCHEMA by default."""
        for cls in (OrderModel, FillModel, PositionModel):
            assert cls.create_table_sql() == cls.SCHEMA
