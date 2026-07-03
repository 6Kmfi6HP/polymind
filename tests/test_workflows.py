"""
Tests for WorkflowCommand and CommandType.
"""

from __future__ import annotations

from datetime import datetime, timezone

from polymind.core.workflows import CommandType, WorkflowCommand


class TestCommandType:
    def test_lifecycle_commands(self):
        assert CommandType.START != CommandType.STOP
        assert CommandType.PAUSE != CommandType.RESUME

    def test_pair_lifecycle_commands(self):
        assert CommandType.SPLIT in CommandType
        assert CommandType.MERGE in CommandType
        assert CommandType.REDEEM in CommandType
        assert CommandType.SELL_REMAINDER in CommandType
        assert CommandType.ONE_SIDED_HALT in CommandType

    def test_all_commands_defined(self):
        expected = {
            "START",
            "STOP",
            "PAUSE",
            "RESUME",
            "RESTART",
            "SPLIT",
            "MERGE",
            "REDEEM",
            "SELL_REMAINDER",
            "ONE_SIDED_HALT",
        }
        assert {e.name for e in CommandType} == expected


class TestWorkflowCommand:
    def test_minimal_construction(self):
        cmd = WorkflowCommand(
            workflow_id="wf-amm-001",
            command=CommandType.START,
            reason="Starting AMM strategy",
        )
        assert cmd.workflow_id == "wf-amm-001"
        assert cmd.command == CommandType.START
        assert cmd.reason == "Starting AMM strategy"
        assert cmd.timestamp is not None
        assert cmd.params == {}

    def test_stop_command(self):
        cmd = WorkflowCommand(
            workflow_id="wf-event-002",
            command=CommandType.STOP,
            reason="Max drawdown reached",
        )
        assert cmd.reason == "Max drawdown reached"
        assert cmd.params == {}

    def test_with_params(self):
        cmd = WorkflowCommand(
            workflow_id="wf-maker-rebate-003",
            command=CommandType.MERGE,
            reason="Scheduled merge",
            params={"outcome": "YES", "token_ids": ["123", "456"]},
        )
        assert cmd.params["outcome"] == "YES"
        assert cmd.params["token_ids"] == ["123", "456"]

    def test_timestamp_auto_set(self):
        before = datetime.now(timezone.utc)
        cmd = WorkflowCommand(
            workflow_id="wf-test",
            command=CommandType.START,
            reason="test",
        )
        after = datetime.now(timezone.utc)
        assert before <= cmd.timestamp <= after

    def test_restart_command(self):
        cmd = WorkflowCommand(
            workflow_id="wf-bands-004",
            command=CommandType.RESTART,
            reason="Reconnecting after disconnect",
        )
        assert cmd.command == CommandType.RESTART
