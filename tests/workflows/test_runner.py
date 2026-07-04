"""
Tests for WorkflowRunner command routing and state management.
"""

from __future__ import annotations

import pytest

from polymind.core.workflows import CommandType, WorkflowCommand
from polymind.workflows.copy_trade.state_machine import CopyTradeState
from polymind.workflows.event_mm.state_machine import EventMMState
from polymind.workflows.maker_rebate.state_machine import RebateState
from polymind.workflows.runner import WorkflowRunner
from polymind.workflows.sniper.state_machine import SniperState


def _cmd(
    workflow_id: str,
    command: CommandType,
    **params,
) -> WorkflowCommand:
    return WorkflowCommand(
        workflow_id=workflow_id,
        command=command,
        params=params or {},
    )


@pytest.fixture
async def runner() -> WorkflowRunner:
    """Fresh WorkflowRunner with no pre-existing instances."""
    return WorkflowRunner()


class TestWorkflowRunnerStart:
    """Tests for START command."""

    async def test_initial_state(self, runner: WorkflowRunner):
        assert runner.list_instances() == {}

    async def test_start_rebate(self, runner: WorkflowRunner):
        cmd = _cmd("rebate-001", CommandType.START, type="maker_rebate")
        result = await runner.process_command(cmd)
        assert result.success is True
        assert result.state == RebateState.PLACING_ORDERS.name

    async def test_start_event_mm(self, runner: WorkflowRunner):
        cmd = _cmd("event_mm-001", CommandType.START, type="event_mm")
        result = await runner.process_command(cmd)
        assert result.success is True
        assert result.state == EventMMState.WATCHING.name

    async def test_start_copy_trade(self, runner: WorkflowRunner):
        cmd = _cmd("copy_trade-001", CommandType.START, type="copy_trade")
        result = await runner.process_command(cmd)
        assert result.success is True
        assert result.state == CopyTradeState.MONITORING.name

    async def test_start_sniper(self, runner: WorkflowRunner):
        cmd = _cmd("sniper-001", CommandType.START, type="sniper")
        result = await runner.process_command(cmd)
        assert result.success is True
        assert result.state == SniperState.WATCHING.name

    async def test_start_duplicate_fails(self, runner: WorkflowRunner):
        cmd = _cmd("rebate-001", CommandType.START, type="maker_rebate")
        await runner.process_command(cmd)
        result = await runner.process_command(cmd)
        assert result.success is False
        assert "already running" in result.message

    async def test_start_unknown_type(self, runner: WorkflowRunner):
        cmd = _cmd("wf-001", CommandType.START, type="nonexistent")
        result = await runner.process_command(cmd)
        assert result.success is False

    async def test_start_no_type_no_prefix(self, runner: WorkflowRunner):
        cmd = _cmd("unknown-001", CommandType.START)
        result = await runner.process_command(cmd)
        assert result.success is False


class TestWorkflowRunnerLifecycle:
    """Tests for lifecycle commands (STOP, PAUSE, RESUME, RESTART)."""

    async def test_stop_workflow(self, runner: WorkflowRunner):
        start = _cmd("rebate-001", CommandType.START, type="maker_rebate")
        await runner.process_command(start)

        stop = _cmd("rebate-001", CommandType.STOP)
        result = await runner.process_command(stop)
        assert result.success is True
        assert result.state == RebateState.HALTED.name

    async def test_pause_resume(self, runner: WorkflowRunner):
        start = _cmd("rebate-001", CommandType.START, type="maker_rebate")
        await runner.process_command(start)

        pause = _cmd("rebate-001", CommandType.PAUSE)
        result = await runner.process_command(pause)
        assert result.success is True
        assert result.state == RebateState.HALTED.name

        resume = _cmd("rebate-001", CommandType.RESUME)
        result = await runner.process_command(resume)
        assert result.success is True
        assert result.state == RebateState.IDLE.name

    async def test_restart(self, runner: WorkflowRunner):
        start = _cmd("rebate-001", CommandType.START, type="maker_rebate")
        await runner.process_command(start)

        restart = _cmd("rebate-001", CommandType.RESTART)
        result = await runner.process_command(restart)
        assert result.success is True
        assert result.state == RebateState.PLACING_ORDERS.name

    async def test_command_on_nonexistent(self, runner: WorkflowRunner):
        cmd = _cmd("nonexistent", CommandType.STOP)
        result = await runner.process_command(cmd)
        assert result.success is False
        assert "not found" in result.message

    async def test_command_on_terminal(self, runner: WorkflowRunner):
        """Sniper has a simple path to COMPLETED via POSITION_SOLD."""
        start = _cmd("sniper-001", CommandType.START, type="sniper")
        await runner.process_command(start)

        # DISCOUNT_SIGNAL -> OPPORTUNITY_DETECTED
        sm = runner.get_instance("sniper-001")
        from polymind.workflows.sniper.state_machine import SniperEvent

        sm.transition(SniperEvent.DISCOUNT_SIGNAL)
        sm.transition(SniperEvent.ORDER_PLACED)
        sm.transition(SniperEvent.POSITION_SOLD)  # -> COMPLETED

        # Now any command should fail
        cmd = _cmd("sniper-001", CommandType.STOP)
        result = await runner.process_command(cmd)
        assert result.success is False
        assert "terminal" in result.message


class TestWorkflowRunnerInstanceManagement:
    """Tests for get_instance, list_instances, shutdown."""

    async def test_get_instance(self, runner: WorkflowRunner):
        cmd = _cmd("rebate-001", CommandType.START, type="maker_rebate")
        await runner.process_command(cmd)
        sm = runner.get_instance("rebate-001")
        assert sm is not None
        assert sm.state.name == RebateState.PLACING_ORDERS.name

    async def test_get_instance_nonexistent(self, runner: WorkflowRunner):
        assert runner.get_instance("nope") is None

    async def test_list_instances(self, runner: WorkflowRunner):
        await runner.process_command(_cmd("rebate-001", CommandType.START, type="maker_rebate"))
        await runner.process_command(_cmd("event_mm-001", CommandType.START, type="event_mm"))
        instances = runner.list_instances()
        assert len(instances) == 2
        assert "rebate-001" in instances
        assert "event_mm-001" in instances

    async def test_shutdown_clears(self, runner: WorkflowRunner):
        await runner.process_command(_cmd("rebate-001", CommandType.START, type="maker_rebate"))
        await runner.shutdown()
        assert runner.list_instances() == {}


class TestWorkflowRunnerTypeInference:
    """Tests for prefix-based type inference."""

    async def test_rebate_prefix(self, runner: WorkflowRunner):
        cmd = _cmd("rebate-my-workflow", CommandType.START)
        result = await runner.process_command(cmd)
        assert result.success is True
        assert result.state == RebateState.PLACING_ORDERS.name

    async def test_event_mm_prefix(self, runner: WorkflowRunner):
        cmd = _cmd("event_mm-my-workflow", CommandType.START)
        result = await runner.process_command(cmd)
        assert result.success is True
        assert result.state == EventMMState.WATCHING.name

    async def test_copy_trade_prefix(self, runner: WorkflowRunner):
        cmd = _cmd("copy_trade-my-workflow", CommandType.START)
        result = await runner.process_command(cmd)
        assert result.success is True
        assert result.state == CopyTradeState.MONITORING.name

    async def test_sniper_prefix(self, runner: WorkflowRunner):
        cmd = _cmd("sniper-my-workflow", CommandType.START)
        result = await runner.process_command(cmd)
        assert result.success is True
        assert result.state == SniperState.WATCHING.name


class TestWorkflowRunnerErrorTransitions:
    """Tests for invalid transitions."""

    async def test_invalid_transition_returns_fail(self, runner: WorkflowRunner):
        # START a rebate, then try PAUSE twice (PAUSE already applied -> HALT,
        # second PAUSE is invalid from HALTED — actually HALTED accepts HALT
        # in this machine. So use STOP from COMPLETED by going full cycle.)
        start = _cmd("rebate-001", CommandType.START, type="maker_rebate")
        await runner.process_command(start)

        # Get the SM directly and drive it to a state where STOP/HALT is invalid.
        # From MERGING, HALT is not a valid transition → gives ValueError.
        sm = runner.get_instance("rebate-001")
        from polymind.workflows.maker_rebate.state_machine import RebateEvent

        sm.transition(RebateEvent.ORDERS_PLACED)
        sm.transition(RebateEvent.ALL_FILLED)
        sm.transition(RebateEvent.MERGE_DONE)  # -> MERGING

        # STOP (HALT) from MERGING is invalid → fails gracefully
        stop = _cmd("rebate-001", CommandType.STOP)
        result = await runner.process_command(stop)
        assert result.success is False

    async def test_start_then_invalid_resume_fails(self, runner: WorkflowRunner):
        """RESUME from non-HALTED state is invalid → fails."""
        start = _cmd("rebate-001", CommandType.START, type="maker_rebate")
        await runner.process_command(start)

        resume = _cmd("rebate-001", CommandType.RESUME)
        result = await runner.process_command(resume)
        assert result.success is False
