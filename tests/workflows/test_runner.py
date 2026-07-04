"""
Tests for WorkflowRunner command routing and state management.
"""

from __future__ import annotations

from enum import Enum

import pytest

from polymind.core.workflows import CommandType, WorkflowCommand
from polymind.workflows.copy_trade.state_machine import CopyTradeState
from polymind.workflows.event_mm.state_machine import EventMMState
from polymind.workflows.maker_rebate.state_machine import RebateState
from polymind.workflows.runner import WorkflowRunner
from polymind.workflows.sniper.state_machine import SniperState


class _BadEv(Enum):
    """Module-level event for BadSM (name ends in 'Ev' not 'Event')."""

    START = "start"


class _NoStartEvent(Enum):
    """*Event-named enum without START, for _resolve_event_enum fallback (line 400)."""

    HALT = "halt"


class _StartEvent(Enum):
    """*Event-named enum with START, for transition ValueError path (line 404-405)."""

    START = "start"


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

    # ── New: cover _resolve_wtype cached type path (line 176) ──────────

    async def test_type_resolution_cached_type(self, runner: WorkflowRunner):
        """_resolve_wtype returns cached type from _types dict."""
        cmd = _cmd("rebate-001", CommandType.START, type="maker_rebate")
        await runner.process_command(cmd)
        # Second start attempt (duplicate) hits cached type via _types
        result = await runner.process_command(cmd)
        assert result.success is False

    async def test_type_resolution_no_type_no_prefix(self, runner: WorkflowRunner):
        """_resolve_wtype returns None when no type hint exists."""
        cmd = _cmd("noprefix-001", CommandType.START)
        result = await runner.process_command(cmd)
        assert result.success is False
        assert "Cannot determine" in result.message

    # ── New: cover _lookup_sm registry path with no Event attr (line 190) ──

    async def test_lookup_sm_registry_no_event(self, runner: WorkflowRunner):
        """_lookup_sm falls back to hardcoded map when registry entry has no Event."""
        from polymind.core.plugin import PluginRegistry

        PluginRegistry.reset()
        registry = PluginRegistry()

        class FakeSM:
            pass  # no Event enum

        registry.register_workflow("fake_type", FakeSM)
        runner = WorkflowRunner(registry=registry)
        cmd = _cmd("wf-001", CommandType.START, type="fake_type")
        result = await runner.process_command(cmd)
        # Falls through to hardcoded map → not found → fail
        assert result.success is False
        assert "Unknown" in result.message

    # ── New: cover unsupported command in _handle_existing (line 362) ──

    async def test_unsupported_command_fails(self, runner: WorkflowRunner):
        """Command that has no matching event enum member fails."""
        # START first
        start = _cmd("rebate-001", CommandType.START, type="maker_rebate")
        await runner.process_command(start)

        # RESTART goes through _handle_restart, but an unknown / unsupported
        # pair command on an existing instance should fail at line 362.
        # Use a command that doesn't go through the pair path but targets
        # existing instance with an unsupported event.
        # RESUME from non-HALTED is already tested; let's test REDEEM on
        # an instance without a pair lifecycle = targets existing instance
        # but pair commands are caught by _is_pair_command first.
        # SPLIT on existing instance without pair lifecycle.
        cmd = _cmd("rebate-001", CommandType.SPLIT)
        result = await runner.process_command(cmd)
        assert result.success is False

    # ── New: cover _handle_start ValueError caught (lines 240-243) ─────

    async def test_start_with_bad_workflow_type_event(self, runner: WorkflowRunner):
        """A workflow type with missing START event."""
        from enum import Enum

        from polymind.core.plugin import PluginRegistry

        PluginRegistry.reset()
        registry = PluginRegistry()

        class NoStartEvent(Enum):
            FOO = "foo"

        class FakeSMNoStart:
            state = NoStartEvent.FOO
            Event = NoStartEvent

            def __init__(self, workflow_id):
                pass

            def transition(self, event):
                pass

            def reset(self):
                pass

            def is_terminal(self):
                return False

        registry.register_workflow("no_start", FakeSMNoStart)
        runner = WorkflowRunner(registry=registry)
        cmd = _cmd("wf-001", CommandType.START, type="no_start")
        result = await runner.process_command(cmd)
        assert result.success is False
        assert "no START event" in result.message

    # ── New: cover _handle_restart error paths (lines 396, 400, 404-405) ─

    async def test_restart_unknown_event_enum(self, runner: WorkflowRunner):
        """RESTART on a SM whose type is not in hardcoded map (line 396)."""
        sm = type("StrangeSM", (), {})()
        sm.state = type("S", (), {"name": "ODD"})()
        sm.reset = lambda: None
        sm.is_terminal = lambda: False
        sm.transition = lambda e: None
        runner._instances["custom-001"] = sm

        cmd = _cmd("custom-001", CommandType.RESTART)
        result = await runner.process_command(cmd)

        # sm_type is "StrangeSM" whose module has no *Event fallback (? depends
        # on module-level enums). At minimum it reaches _resolve_event_enum.
        assert result.success is False

    async def test_restart_transition_fails(self, runner: WorkflowRunner):
        """RESTART where transition(start) raises ValueError (line 404-405)."""
        start = _cmd("sniper-002", CommandType.START, type="sniper")
        await runner.process_command(start)

        # Monkey-patch transition on the STARTed SM
        sm = runner.get_instance("sniper-002")

        def bad_transition(event):
            raise ValueError("restart failed")

        sm.transition = bad_transition

        cmd = _cmd("sniper-002", CommandType.RESTART)
        result = await runner.process_command(cmd)
        assert result.success is False
