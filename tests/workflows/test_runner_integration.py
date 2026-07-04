"""
Integration tests for WorkflowRunner with PluginRegistry.
"""

from __future__ import annotations

import pytest

from polymind.core.plugin import PluginRegistry
from polymind.core.workflows import CommandType, WorkflowCommand
from polymind.workflows.maker_rebate.state_machine import (
    RebateState,
    RebateStateMachine,
)
from polymind.workflows.runner import WorkflowRunner


@pytest.fixture
def plugin_registry() -> PluginRegistry:
    PluginRegistry.reset()
    return PluginRegistry()


@pytest.fixture
async def runner_with_registry(plugin_registry: PluginRegistry) -> WorkflowRunner:
    plugin_registry.register_workflow(
        "maker_rebate",
        RebateStateMachine,
    )
    return WorkflowRunner(registry=plugin_registry)


class TestWorkflowRunnerIntegration:
    """End-to-end tests: PluginRegistry → WorkflowRunner → state machine."""

    async def test_runner_uses_registry(self, runner_with_registry: WorkflowRunner):
        cmd = WorkflowCommand(
            workflow_id="rebate-001",
            command=CommandType.START,
            params={"type": "maker_rebate"},
        )
        result = await runner_with_registry.process_command(cmd)
        assert result.success is True
        assert result.state == RebateState.PLACING_ORDERS.name

    async def test_runner_instance_list(self, runner_with_registry: WorkflowRunner):
        await runner_with_registry.process_command(
            WorkflowCommand(
                workflow_id="rebate-001",
                command=CommandType.START,
                params={"type": "maker_rebate"},
            ),
        )
        await runner_with_registry.process_command(
            WorkflowCommand(
                workflow_id="rebate-002",
                command=CommandType.START,
                params={"type": "maker_rebate"},
            ),
        )

        instances = runner_with_registry.list_instances()
        assert len(instances) == 2

    async def test_runner_shutdown(self, runner_with_registry: WorkflowRunner):
        await runner_with_registry.process_command(
            WorkflowCommand(
                workflow_id="rebate-001",
                command=CommandType.START,
                params={"type": "maker_rebate"},
            ),
        )
        await runner_with_registry.shutdown()
        assert runner_with_registry.list_instances() == {}
