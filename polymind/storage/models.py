"""Domain model definitions for the storage layer.

Each model maps to a database table and knows how to serialise
to/from plain dicts and generate its own DDL.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Self


class DBModel(ABC):
    """Abstract base for all storage models.

    Subclasses must define *SCHEMA* and implement *tablename*,
    *to_dict* and *from_dict*.
    """

    SCHEMA: str = ""

    @classmethod
    @abstractmethod
    def tablename(cls) -> str:
        """Return the database table name for this model."""

    @abstractmethod
    def to_dict(self) -> dict[str, Any]:
        """Serialise the model instance to a plain dictionary."""

    @classmethod
    @abstractmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        """Deserialise a dictionary back into a model instance."""

    @classmethod
    def create_table_sql(cls) -> str:
        """Return the DDL statement that creates this model's table."""
        return cls.SCHEMA


@dataclass
class OrderModel(DBModel):
    """A single order placed on the exchange."""

    order_id: str
    market_id: str
    token_id: str
    side: str
    price: float
    size: float
    status: str
    created_at: datetime
    updated_at: datetime

    SCHEMA: str = """CREATE TABLE IF NOT EXISTS orders (
    order_id    TEXT PRIMARY KEY,
    market_id   TEXT NOT NULL,
    token_id    TEXT NOT NULL,
    side        TEXT NOT NULL,
    price       REAL NOT NULL,
    size        REAL NOT NULL,
    status      TEXT NOT NULL,
    created_at  TEXT NOT NULL,
    updated_at  TEXT NOT NULL
)"""

    @classmethod
    def tablename(cls) -> str:
        return "orders"

    def to_dict(self) -> dict[str, Any]:
        return {
            "order_id": self.order_id,
            "market_id": self.market_id,
            "token_id": self.token_id,
            "side": self.side,
            "price": self.price,
            "size": self.size,
            "status": self.status,
            "created_at": self.created_at.isoformat(),
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        return cls(
            order_id=data["order_id"],
            market_id=data["market_id"],
            token_id=data["token_id"],
            side=data["side"],
            price=data["price"],
            size=data["size"],
            status=data["status"],
            created_at=datetime.fromisoformat(data["created_at"]),
            updated_at=datetime.fromisoformat(data["updated_at"]),
        )


@dataclass
class FillModel(DBModel):
    """A recorded fill (partial or full) for an order."""

    fill_id: str
    order_id: str
    market_id: str
    side: str
    price: float
    size: float
    fee: float
    timestamp: datetime

    SCHEMA: str = """CREATE TABLE IF NOT EXISTS fills (
    fill_id     TEXT PRIMARY KEY,
    order_id    TEXT NOT NULL,
    market_id   TEXT NOT NULL,
    side        TEXT NOT NULL,
    price       REAL NOT NULL,
    size        REAL NOT NULL,
    fee         REAL NOT NULL,
    timestamp   TEXT NOT NULL
)"""

    @classmethod
    def tablename(cls) -> str:
        return "fills"

    def to_dict(self) -> dict[str, Any]:
        return {
            "fill_id": self.fill_id,
            "order_id": self.order_id,
            "market_id": self.market_id,
            "side": self.side,
            "price": self.price,
            "size": self.size,
            "fee": self.fee,
            "timestamp": self.timestamp.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        return cls(
            fill_id=data["fill_id"],
            order_id=data["order_id"],
            market_id=data["market_id"],
            side=data["side"],
            price=data["price"],
            size=data["size"],
            fee=data["fee"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
        )


@dataclass
class PositionModel(DBModel):
    """An open position in a given market/token."""

    market_id: str
    token_id: str
    size: float
    avg_entry: float
    realized_pnl: float
    updated_at: datetime

    SCHEMA: str = """CREATE TABLE IF NOT EXISTS positions (
    market_id    TEXT NOT NULL,
    token_id     TEXT NOT NULL,
    size         REAL NOT NULL,
    avg_entry    REAL NOT NULL,
    realized_pnl REAL NOT NULL,
    updated_at   TEXT NOT NULL,
    PRIMARY KEY (market_id, token_id)
)"""

    @classmethod
    def tablename(cls) -> str:
        return "positions"

    def to_dict(self) -> dict[str, Any]:
        return {
            "market_id": self.market_id,
            "token_id": self.token_id,
            "size": self.size,
            "avg_entry": self.avg_entry,
            "realized_pnl": self.realized_pnl,
            "updated_at": self.updated_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> Self:
        return cls(
            market_id=data["market_id"],
            token_id=data["token_id"],
            size=data["size"],
            avg_entry=data["avg_entry"],
            realized_pnl=data["realized_pnl"],
            updated_at=datetime.fromisoformat(data["updated_at"]),
        )
