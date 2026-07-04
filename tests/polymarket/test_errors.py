"""Tests for Polymarket adapter error hierarchy."""

from __future__ import annotations

import pytest

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


class TestErrorConstruction:
    """Each error type can be constructed and raised."""

    @pytest.mark.parametrize(
        "exc_class",
        [
            PolymarketError,
            AuthenticationError,
            InsufficientAuthError,
            MarketNotFoundError,
            OrderRejectedError,
            RateLimitError,
            ConnectionError,
            ContractError,
            NonceTooLowError,
            InsufficientGasError,
        ],
    )
    def test_default_construction(self, exc_class):
        exc = exc_class()
        assert isinstance(exc, exc_class)

    @pytest.mark.parametrize(
        "exc_class,msg",
        [
            (PolymarketError, "base error"),
            (AuthenticationError, "bad key"),
            (InsufficientAuthError, "need tier 2"),
            (MarketNotFoundError, "0xdead not found"),
            (OrderRejectedError, "price too low"),
            (RateLimitError, "too fast"),
            (ConnectionError, "timeout"),
            (ContractError, "revert"),
            (NonceTooLowError, "nonce 5 < 9"),
            (InsufficientGasError, "0 MATIC"),
        ],
    )
    def test_message_passthrough(self, exc_class, msg):
        exc = exc_class(msg)
        assert str(exc) == msg
        assert exc.args[0] == msg


class TestRateLimitError:
    """RateLimitError stores retry_after."""

    def test_default_retry_after(self):
        exc = RateLimitError()
        assert exc.retry_after == 0.0

    def test_custom_retry_after(self):
        exc = RateLimitError("rate limited", retry_after=5.5)
        assert exc.retry_after == 5.5

    def test_message_and_retry(self):
        exc = RateLimitError("slow down", retry_after=2.0)
        assert str(exc) == "slow down"
        assert exc.retry_after == 2.0


class TestInheritanceHierarchy:
    """Verify the exception inheritance chain."""

    # AuthenticationError is a PolymarketError
    def test_auth_error_is_polymarket_error(self):
        exc = AuthenticationError()
        assert isinstance(exc, PolymarketError)

    # NonceTooLowError is a ContractError is a PolymarketError
    def test_nonce_too_low_inheritance(self):
        exc = NonceTooLowError()
        assert isinstance(exc, NonceTooLowError)
        assert isinstance(exc, ContractError)
        assert isinstance(exc, PolymarketError)

    # InsufficientGasError is a ContractError is a PolymarketError
    def test_insufficient_gas_inheritance(self):
        exc = InsufficientGasError()
        assert isinstance(exc, InsufficientGasError)
        assert isinstance(exc, ContractError)
        assert isinstance(exc, PolymarketError)

    # InsufficientAuthError is a PolymarketError (not ContractError)
    def test_insufficient_auth_not_contract_error(self):
        exc = InsufficientAuthError()
        assert isinstance(exc, PolymarketError)
        assert not isinstance(exc, ContractError)

    # ContractError is a PolymarketError
    def test_contract_error_is_polymarket_error(self):
        exc = ContractError()
        assert isinstance(exc, PolymarketError)

    # MarketNotFoundError is a PolymarketError (not ContractError)
    def test_market_not_found_not_contract_error(self):
        exc = MarketNotFoundError()
        assert isinstance(exc, PolymarketError)
        assert not isinstance(exc, ContractError)

    # OrderRejectedError is a PolymarketError (not ContractError)
    def test_order_rejected_not_contract_error(self):
        exc = OrderRejectedError()
        assert isinstance(exc, PolymarketError)
        assert not isinstance(exc, ContractError)

    # RateLimitError is a PolymarketError (not ContractError)
    def test_rate_limit_not_contract_error(self):
        exc = RateLimitError()
        assert isinstance(exc, PolymarketError)
        assert not isinstance(exc, ContractError)

    # ConnectionError is a PolymarketError (not ContractError)
    def test_connection_error_not_contract_error(self):
        exc = ConnectionError()
        assert isinstance(exc, PolymarketError)
        assert not isinstance(exc, ContractError)

    # All error types are Exception subclasses
    def test_all_are_exceptions(self):
        for exc in [
            PolymarketError(),
            AuthenticationError(),
            InsufficientAuthError(),
            MarketNotFoundError(),
            OrderRejectedError(),
            RateLimitError(),
            ConnectionError(),
            ContractError(),
            NonceTooLowError(),
            InsufficientGasError(),
        ]:
            assert isinstance(exc, Exception)


class TestCatchByBaseType:
    """Exceptions can be caught by PolymarketError."""

    def test_catch_specific_with_base(self):
        raised_exc = None
        try:
            raise AuthenticationError("fail")
        except PolymarketError as e:
            raised_exc = e
        assert isinstance(raised_exc, AuthenticationError)
        assert str(raised_exc) == "fail"

    def test_catch_all_polymarket_errors(self):
        errors = [
            AuthenticationError(),
            InsufficientAuthError(),
            MarketNotFoundError(),
            OrderRejectedError(),
            RateLimitError(),
            ConnectionError(),
            ContractError(),
            NonceTooLowError(),
            InsufficientGasError(),
        ]
        for exc in errors:
            caught = False
            try:
                raise exc
            except PolymarketError:
                caught = True
            assert caught, f"{type(exc).__name__} not caught by PolymarketError"

    def test_raise_and_catch_rate_limit(self):
        with pytest.raises(RateLimitError) as excinfo:
            raise RateLimitError("api limit", retry_after=3.0)
        assert excinfo.value.retry_after == 3.0
        assert str(excinfo.value) == "api limit"

    def test_raise_and_catch_contract_chain(self):
        with pytest.raises(ContractError):
            raise NonceTooLowError("nonce mismatch")
        with pytest.raises(ContractError):
            raise InsufficientGasError("no gas")
        with pytest.raises(PolymarketError):
            raise NonceTooLowError("nonce")
        with pytest.raises(PolymarketError):
            raise InsufficientGasError("gas")


class TestStringRepresentation:
    """String representation includes message."""

    @pytest.mark.parametrize(
        "exc,expected",
        [
            (PolymarketError("msg"), "msg"),
            (AuthenticationError("auth fail"), "auth fail"),
            (RateLimitError("slow", retry_after=1.0), "slow"),
        ],
    )
    def test_str_contains_message(self, exc, expected):
        assert str(exc) == expected
