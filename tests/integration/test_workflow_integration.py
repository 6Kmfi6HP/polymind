"""
Integration: WorkflowRunner + PairLifecycleManager.

Verifies the WorkflowRunner can start/halt workflow instances and delegate
pair commands to PairLifecycleManager.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from polymind.core.workflows import CommandType, WorkflowCommand
from polymind.polymarket.contracts import ContractsGateway, OnChainBalance, SplitResult
from polymind.polymarket.pair_lifecycle import PairLifecycleManager
from polymind.workflows.runner import WorkflowRunner


@pytest.fixture
def mock_gateway() -> MagicMock:
    gw = MagicMock(spec=ContractsGateway)
    gw.get_onchain_balance = AsyncMock()
    gw.split = AsyncMock()
    gw.approve_usdc = AsyncMock()
    return gw


@pytest.fixture
def pair_lifecycle(mock_gateway: MagicMock) -> PairLifecycleManager:
    return PairLifecycleManager(gateway=mock_gateway)


@pytest.fixture
def runner(pair_lifecycle: PairLifecycleManager) -> WorkflowRunner:
    return WorkflowRunner(pair_lifecycle=pair_lifecycle)


class TestWorkflowIntegration:
    async def test_start_maker_rebate_workflow(self, runner: WorkflowRunner):
        cmd = WorkflowCommand(
            workflow_id="rebate-001",
            command=CommandType.START,
            params={"type": "maker_rebate"},
        )
        result = await runner.process_command(cmd)

        assert result.success is True
        assert result.state == "PLACING_ORDERS"
        instances = runner.list_instances()
        assert "rebate-001" in instances

    async def test_halt_workflow(self, runner: WorkflowRunner):
        start = WorkflowCommand(
            workflow_id="rebate-001",
            command=CommandType.START,
            params={"type": "maker_rebate"},
        )
        await runner.process_command(start)

        stop = WorkflowCommand(
            workflow_id="rebate-001",
            command=CommandType.STOP,
        )
        result = await runner.process_command(stop)

        assert result.success is True
        assert result.state == "HALTED"

    async def test_prefix_inference(self, runner: WorkflowRunner):
        """Workflow ID prefix rebate-* should infer type."""
        cmd = WorkflowCommand(
            workflow_id="rebate-auto",
            command=CommandType.START,
        )
        result = await runner.process_command(cmd)
        assert result.success is True
        assert result.state == "PLACING_ORDERS"

    async def test_split_via_runner(
        self,
        runner: WorkflowRunner,
        mock_gateway: MagicMock,
    ):
        """Pair command SPLIT delegated to PairLifecycleManager."""
        # Register a market on the underlying manager
        runner._pair_lifecycle.register_market(
            condition_id="0xabc",
            yes_token_id="111",
            no_token_id="222",
        )

        mock_gateway.get_onchain_balance.return_value = OnChainBalance(
            token_id="111",
            balance=0,
            usdc_balance=500.0,
        )
        mock_gateway.split.return_value = SplitResult(
            tx_hash="0xsplit",
            outcome_a_amount=25.0,
            outcome_b_amount=25.0,
        )

        cmd = WorkflowCommand(
            workflow_id="rebate-001",
            command=CommandType.SPLIT,
            params={"condition_id": "0xabc", "amount": 50_000_000},
        )
        result = await runner.process_command(cmd)

        assert result.success is True
        assert "Split 50.0 USDC" in result.message
