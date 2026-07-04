"""
Tests for WorkflowRunner pair command delegation to PairLifecycleManager.
"""

from __future__ import annotations

from unittest.mock import AsyncMock

import pytest

from polymind.core.workflows import CommandType, WorkflowCommand
from polymind.polymarket.pair_lifecycle import (
    MergeOperation,
    OneSidedHaltResult,
    PairLifecycleManager,
    PairPosition,
    RedeemOperation,
    SellRemainderOperation,
    SplitOperation,
)
from polymind.workflows.runner import WorkflowRunner


def _cmd(workflow_id: str, command: CommandType, **params) -> WorkflowCommand:
    return WorkflowCommand(workflow_id=workflow_id, command=command, params=params or {})


@pytest.fixture
def mock_pair_lifecycle() -> AsyncMock:
    mgr = AsyncMock(spec=PairLifecycleManager)
    mgr.split = AsyncMock()
    mgr.merge = AsyncMock()
    mgr.redeem = AsyncMock()
    mgr.sell_remainder = AsyncMock()
    mgr.one_sided_halt = AsyncMock()
    return mgr


@pytest.fixture
def runner(mock_pair_lifecycle: AsyncMock) -> WorkflowRunner:
    return WorkflowRunner(pair_lifecycle=mock_pair_lifecycle)


class TestWorkflowRunnerPairCommands:
    """Tests for pair command delegation from WorkflowRunner."""

    async def test_split_command(self, runner: WorkflowRunner, mock_pair_lifecycle: AsyncMock):
        pos = PairPosition(condition_id="0xabc", yes_token_id="1", no_token_id="2")
        mock_pair_lifecycle.split.return_value = SplitOperation(
            condition_id="0xabc",
            usdc_amount=50.0,
            yes_amount=25.0,
            no_amount=25.0,
            tx_hash="0xtx",
            updated_position=pos,
        )

        cmd = _cmd("wf-001", CommandType.SPLIT, condition_id="0xabc", amount=50_000_000)
        result = await runner.process_command(cmd)

        assert result.success is True
        assert "Split 50.0 USDC" in result.message
        mock_pair_lifecycle.split.assert_called_once_with("0xabc", 50_000_000)

    async def test_merge_command(self, runner: WorkflowRunner, mock_pair_lifecycle: AsyncMock):
        pos = PairPosition(condition_id="0xabc", yes_token_id="1", no_token_id="2")
        mock_pair_lifecycle.merge.return_value = MergeOperation(
            condition_id="0xabc",
            outcome_token_amount=25.0,
            proceeds_usdc=25.0,
            tx_hash="0xtx",
            updated_position=pos,
        )

        cmd = _cmd("wf-001", CommandType.MERGE, condition_id="0xabc", amount=25_000_000)
        result = await runner.process_command(cmd)

        assert result.success is True
        assert "Merged 25.0 pairs" in result.message

    async def test_redeem_command(self, runner: WorkflowRunner, mock_pair_lifecycle: AsyncMock):
        pos = PairPosition(condition_id="0xabc", yes_token_id="1", no_token_id="2")
        mock_pair_lifecycle.redeem.return_value = RedeemOperation(
            condition_id="0xabc",
            outcome="YES",
            amount_redeemed=30.0,
            proceeds_usdc=30.0,
            tx_hash="0xtx",
            updated_position=pos,
        )

        cmd = _cmd("wf-001", CommandType.REDEEM, condition_id="0xabc")
        result = await runner.process_command(cmd)

        assert result.success is True
        assert "Redeemed 30.0 YES tokens" in result.message

    async def test_sell_remainder_command(
        self, runner: WorkflowRunner, mock_pair_lifecycle: AsyncMock
    ):
        mock_pair_lifecycle.sell_remainder.return_value = SellRemainderOperation(
            market_id="mkt1",
            outcome="YES",
            amount_sold=4.5,
            orders_placed=1,
        )

        cmd = _cmd("wf-001", CommandType.SELL_REMAINDER, market_id="mkt1", outcome="YES")
        result = await runner.process_command(cmd)

        assert result.success is True
        assert "Sold 4.5 YES tokens" in result.message

    async def test_one_sided_halt_command(
        self, runner: WorkflowRunner, mock_pair_lifecycle: AsyncMock
    ):
        mock_pair_lifecycle.one_sided_halt.return_value = OneSidedHaltResult(
            market_id="mkt1",
            outcome="NO",
            orders_cancelled=3,
        )

        cmd = _cmd("wf-001", CommandType.ONE_SIDED_HALT, market_id="mkt1", outcome="NO")
        result = await runner.process_command(cmd)

        assert result.success is True
        assert "Halted NO side on mkt1" in result.message

    async def test_pair_command_no_manager(self):
        """Without PairLifecycleManager, pair commands should fail."""
        runner = WorkflowRunner()  # no pair_lifecycle

        cmd = _cmd("wf-001", CommandType.SPLIT, condition_id="0xabc", amount=1000)
        result = await runner.process_command(cmd)

        assert result.success is False
        assert "not configured" in result.message

    async def test_pair_command_error(self, runner: WorkflowRunner, mock_pair_lifecycle: AsyncMock):
        mock_pair_lifecycle.split.side_effect = ValueError("split failed")

        cmd = _cmd("wf-001", CommandType.SPLIT, condition_id="0xabc", amount=1000)
        result = await runner.process_command(cmd)

        assert result.success is False
        assert "split failed" in result.message
