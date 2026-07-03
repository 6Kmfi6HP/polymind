"""
Tests for preflight validation and safety mechanisms.
"""

from __future__ import annotations

from datetime import datetime, timezone

import pytest

from polymind.core.intents import CancelIntent, IntentExecutor, OrderIntent, OrderSide, StrategyIntent
from polymind.core.risk import RiskContext
from polymind.execution.safety import KillSwitch, LogRedaction, PreflightChecker, PreflightResult


class TestPreflightChecker:
    @pytest.mark.asyncio
    async def test_empty_intent_valid(self):
        """An empty StrategyIntent should pass preflight."""
        intent = StrategyIntent(
            timestamp=datetime.now(timezone.utc),
            strategy_name="test",
        )
        checker = PreflightChecker()
        result = await checker.check(intent)
        assert result.valid is True
        assert result.errors == []

    @pytest.mark.asyncio
    async def test_negative_price_rejected(self):
        """Orders with negative prices should be rejected."""
        intent = StrategyIntent(
            timestamp=datetime.now(timezone.utc),
            strategy_name="test",
            orders=[
                OrderIntent(
                    market_id="0xabc",
                    side=OrderSide.BUY,
                    price=-0.5,
                    size=10.0,
                ),
            ],
        )
        checker = PreflightChecker()
        result = await checker.check(intent)
        assert result.valid is False
        assert any("price" in err.lower() for err in result.errors)

    @pytest.mark.asyncio
    async def test_negative_size_rejected(self):
        """Orders with negative sizes should be rejected."""
        intent = StrategyIntent(
            timestamp=datetime.now(timezone.utc),
            strategy_name="test",
            orders=[
                OrderIntent(
                    market_id="0xabc",
                    side=OrderSide.BUY,
                    price=0.85,
                    size=-10.0,
                ),
            ],
        )
        checker = PreflightChecker()
        result = await checker.check(intent)
        assert result.valid is False

    @pytest.mark.asyncio
    async def test_zero_price_accepted(self):
        """Zero price should be valid (may be a market order simulation)."""
        intent = StrategyIntent(
            timestamp=datetime.now(timezone.utc),
            strategy_name="test",
            orders=[
                OrderIntent(
                    market_id="0xabc",
                    side=OrderSide.BUY,
                    price=0.0,
                    size=10.0,
                ),
            ],
        )
        checker = PreflightChecker()
        result = await checker.check(intent)
        assert result.valid is True

    @pytest.mark.asyncio
    async def test_valid_intent_passes(self):
        """A normal order should pass."""
        intent = StrategyIntent(
            timestamp=datetime.now(timezone.utc),
            strategy_name="test",
            orders=[
                OrderIntent(
                    market_id="0xabc",
                    side=OrderSide.BUY,
                    price=0.85,
                    size=10.0,
                ),
            ],
        )
        checker = PreflightChecker()
        result = await checker.check(intent)
        assert result.valid is True

    @pytest.mark.asyncio
    async def test_multiple_errors(self):
        """All errors should be reported, not just the first."""
        intent = StrategyIntent(
            timestamp=datetime.now(timezone.utc),
            strategy_name="test",
            orders=[
                OrderIntent(
                    market_id="0xabc",
                    side=OrderSide.BUY,
                    price=-1.0,
                    size=-10.0,
                ),
                OrderIntent(
                    market_id="0xdef",
                    side=OrderSide.SELL,
                    price=-0.5,
                    size=5.0,
                ),
            ],
        )
        checker = PreflightChecker()
        result = await checker.check(intent)
        assert result.valid is False
        assert len(result.errors) >= 2  # at least negative price and negative size

    @pytest.mark.asyncio
    async def test_too_many_orders_rejected(self):
        """Excessive orders per intent should be rejected."""
        checker = PreflightChecker(max_orders_per_intent=2)
        intent = StrategyIntent(
            timestamp=datetime.now(timezone.utc),
            strategy_name="test",
            orders=[
                OrderIntent(market_id="0xa", side=OrderSide.BUY, price=0.5, size=1.0),
                OrderIntent(market_id="0xa", side=OrderSide.SELL, price=0.5, size=1.0),
                OrderIntent(market_id="0xa", side=OrderSide.BUY, price=0.6, size=1.0),
            ],
        )
        result = await checker.check(intent)
        assert result.valid is False
        assert any("order" in err.lower() for err in result.errors)


class TestPreflightResult:
    def test_valid_default(self):
        result = PreflightResult(valid=True, errors=[])
        assert result.valid is True
        assert len(result.errors) == 0

    def test_invalid_with_reasons(self):
        result = PreflightResult(
            valid=False, errors=["negative price", "negative size"]
        )
        assert result.valid is False
        assert len(result.errors) == 2


class TestKillSwitch:
    def test_initial_state(self):
        ks = KillSwitch()
        assert ks.is_active is False

    def test_engage(self):
        ks = KillSwitch()
        ks.engage(reason="max drawdown")
        assert ks.is_active is True
        assert ks.reason == "max drawdown"
        assert ks.engaged_at is not None

    def test_release(self):
        ks = KillSwitch()
        ks.engage(reason="test")
        ks.release()
        assert ks.is_active is False
        assert ks.reason == ""

    def test_double_engage_updates_reason(self):
        ks = KillSwitch()
        ks.engage(reason="first")
        ks.engage(reason="second")
        assert ks.is_active is True
        assert ks.reason == "second"

    def test_engaged_at_timestamp(self):
        from datetime import datetime, timezone

        ks = KillSwitch()
        before = datetime.now(timezone.utc)
        ks.engage(reason="test")
        after = datetime.now(timezone.utc)
        assert before <= ks.engaged_at <= after


class TestLogRedaction:
    def test_redact_api_key(self):
        lr = LogRedaction()
        text = "api_key=sk-abc123def456"
        redacted = lr.redact(text)
        assert "sk-abc123def456" not in redacted
        assert "***" in redacted

    def test_redact_private_key(self):
        lr = LogRedaction()
        text = "private_key = 0x1234567890abcdef"
        redacted = lr.redact(text)
        assert "0x1234567890abcdef" not in redacted
        assert "***" in redacted

    def test_redact_wallet_address(self):
        lr = LogRedaction()
        text = "wallet: 0x742d35Cc6634C0532925a3b844Bc9e7595f2bD18"
        redacted = lr.redact(text)
        assert "0x742d35Cc6634C0532925a3b844Bc9e7595f2bD18" not in redacted

    def test_non_secret_unchanged(self):
        lr = LogRedaction()
        text = "Processing order for market 0xabc"
        redacted = lr.redact(text)
        assert redacted == text

    def test_empty_string(self):
        lr = LogRedaction()
        assert lr.redact("") == ""

    def test_redact_jwt(self):
        lr = LogRedaction()
        text = "token=eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxMjM0NTY3ODkwIn0.dozjgNryP4J3jVNH-Qjc"
        redacted = lr.redact(text)
        assert "eyJ" not in redacted
        assert "***" in redacted
