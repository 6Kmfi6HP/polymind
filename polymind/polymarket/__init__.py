"""Polymarket CLOB integration — client, orders, WebSocket, contracts, data, signing, metrics, errors."""

from polymind.polymarket.client import PolymarketClient
from polymind.polymarket.contracts import (
    ContractsConfig,
    ContractsGateway,
    MergeResult,
    OnChainBalance,
    RedeemResult,
    SplitResult,
    TokenBalance,
    TransactionResult,
)
from polymind.polymarket.data_api import DataAPIConfig, PolymarketDataAPI
from polymind.polymarket.errors import (
    AuthenticationError,
    ConnectionError,
    ContractError,
    InsufficientAuthError,
    InsufficientGasError,
    MarketNotFoundError,
    NonceTooLowError,
    OrderRejectedError,
    PolymarketError,
    RateLimitError,
)
from polymind.polymarket.metrics import AdapterMetrics, Counter, Histogram, MetricsSummary
from polymind.polymarket.signer import (
    ApiKeyCredentials,
    AuthTier,
    Signer,
    WalletCredentials,
)
from polymind.polymarket.types import (
    Candle,
    MarketDetail,
    OrderBookLevel,
    OrderBookSnapshot,
    Trade,
    VolumeInfo,
)
from polymind.polymarket.types import (
    OrderBookLevel as OrderLevel,
)
from polymind.polymarket.types import (
    OrderBookSnapshot as OrderbookSnapshot,
)
from polymind.polymarket.websocket import (
    MarketEvent,
    PolymarketWebSocketAdapter,
    WebSocketChannel,
    WebSocketConfig,
)

__all__ = [
    "PolymarketClient",
    "PolymarketWebSocketAdapter",
    "WebSocketConfig",
    "WebSocketChannel",
    "MarketEvent",
    "PolymarketDataAPI",
    "DataAPIConfig",
    "MarketDetail",
    "OrderBookLevel",  # canonical
    "OrderLevel",  # backward-compat alias
    "OrderBookSnapshot",  # canonical
    "OrderbookSnapshot",  # backward-compat alias
    "Candle",
    "Trade",
    "VolumeInfo",
    "ContractsGateway",
    "ContractsConfig",
    "OnChainBalance",
    "SplitResult",
    "MergeResult",
    "RedeemResult",
    "TokenBalance",
    "TransactionResult",
    "Signer",
    "AuthTier",
    "ApiKeyCredentials",
    "WalletCredentials",
    "AdapterMetrics",
    "Counter",
    "Histogram",
    "MetricsSummary",
    "AuthenticationError",
    "ConnectionError",
    "ContractError",
    "InsufficientAuthError",
    "InsufficientGasError",
    "MarketNotFoundError",
    "NonceTooLowError",
    "OrderRejectedError",
    "PolymarketError",
    "RateLimitError",
]
