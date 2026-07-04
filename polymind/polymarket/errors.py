"""Polymarket adapter error hierarchy.

All adapter modules raise these exceptions (never raw SDK exceptions).
"""


class PolymarketError(Exception):
    """Base for all Polymarket adapter errors."""

    ...


class AuthenticationError(PolymarketError):
    """Invalid or expired API key / wallet credentials."""

    ...


class InsufficientAuthError(PolymarketError):
    """Operation requires a higher auth tier."""

    ...


class MarketNotFoundError(PolymarketError):
    """Requested market or token does not exist."""

    ...


class OrderRejectedError(PolymarketError):
    """CLOB rejected the order (invalid price, size, etc.)."""

    ...


class RateLimitError(PolymarketError):
    """HTTP 429 from CLOB or Data API."""

    def __init__(self, message: str = "", retry_after: float = 0.0):
        self.retry_after = retry_after
        super().__init__(message)


class ConnectionError(PolymarketError):
    """Network-level failure (DNS, timeout, connection refused)."""

    ...


class ContractError(PolymarketError):
    """On-chain transaction reverted or failed."""

    ...


class NonceTooLowError(ContractError):
    """Transaction nonce too low (stale nonce)."""

    ...


class InsufficientGasError(ContractError):
    """Wallet lacks MATIC for gas."""

    ...
