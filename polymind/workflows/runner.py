"""
WorkflowRunner — registry of active workflow instances and command router.

Routes WorkflowCommand (START / STOP / PAUSE / RESUME / RESTART / SPLIT / MERGE
/ REDEEM) to the correct state machine type and returns a CommandResult.

Follows the PaperExecutor pattern: single class with instance registry, async
process_command entry point, and async shutdown for clean teardown.
"""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

from polymind.core.plugin import PluginRegistry
from polymind.core.workflows import CommandType, WorkflowCommand
from polymind.workflows.copy_trade.state_machine import (
    CopyTradeEvent,
    CopyTradeStateMachine,
)
from polymind.workflows.event_mm.state_machine import (
    EventMMEvent,
    EventMMStateMachine,
)
from polymind.workflows.maker_rebate.state_machine import (
    RebateEvent,
    RebateStateMachine,
)
from polymind.workflows.sniper.state_machine import (
    SniperEvent,
    SniperStateMachine,
)

# ── Hardcoded type → (sm_class, event_enum) mapping ──────────────────────

WORKFLOW_TYPE_MAP: dict[str, tuple[type, type]] = {
    "maker_rebate": (RebateStateMachine, RebateEvent),
    "event_mm": (EventMMStateMachine, EventMMEvent),
    "copy_trade": (CopyTradeStateMachine, CopyTradeEvent),
    "sniper": (SniperStateMachine, SniperEvent),
}

# Shared lifecycle commands: CommandType → event-name string.
# Every state machine's event enum defines START / HALT / RESUME.
COMMAND_TO_EVENT: dict[CommandType, str] = {
    CommandType.START: "START",
    CommandType.STOP: "HALT",
    CommandType.PAUSE: "HALT",
    CommandType.RESUME: "RESUME",
}

# Pair-lifecycle commands that only apply to certain workflow types.
PAIR_COMMAND_MAP: dict[str, str] = {
    "SPLIT": "MERGE_DONE",
    "MERGE": "MERGE_DONE",
    "REDEEM": "REDEEM_DONE",
}

# ── Type inference helpers ───────────────────────────────────────────────

TYPE_PREFIX_MAP: dict[str, str] = {
    "rebate-": "maker_rebate",
    "event_mm-": "event_mm",
    "copy_trade-": "copy_trade",
    "sniper-": "sniper",
}


def _infer_workflow_type(workflow_id: str) -> str | None:
    """Infer workflow type from *workflow_id* prefix conventions."""
    for prefix, wtype in TYPE_PREFIX_MAP.items():
        if workflow_id.startswith(prefix):
            return wtype
    return None


# ── Result type ──────────────────────────────────────────────────────────


@dataclass
class CommandResult:
    """Outcome of processing a single WorkflowCommand."""

    workflow_id: str
    command: CommandType
    success: bool
    state: str = ""
    previous_state: str = ""
    message: str = ""
    instance_count: int = 0


# ── Runner ───────────────────────────────────────────────────────────────


class WorkflowRunner:
    """Registry of active workflow instances and command router.

    Owns zero or more state machine instances keyed by *workflow_id* and
    routes :class:`WorkflowCommand` to the correct machine.

    Parameters
    ----------
    registry:
        Optional :class:`PluginRegistry` for custom workflow types.
        Falls back to a hardcoded type map when the registry has no
        matching entry.
    """

    def __init__(self, registry: PluginRegistry | None = None) -> None:
        self._instances: dict[str, Any] = {}
        self._types: dict[str, str] = {}  # workflow_id -> type_name
        self._registry = registry or PluginRegistry()

    # ── Public API ────────────────────────────────────────────────────

    async def process_command(self, cmd: WorkflowCommand) -> CommandResult:
        """Route *cmd* to the correct state machine and apply the transition.

        Returns a :class:`CommandResult` describing the outcome.
        """
        if cmd.command == CommandType.START:
            return self._handle_start(cmd)
        return self._handle_existing(cmd)

    def get_instance(self, workflow_id: str) -> Any | None:
        """Return the active state machine instance, if any."""
        return self._instances.get(workflow_id)

    def list_instances(self) -> dict[str, str]:
        """Return ``{workflow_id: state_name}`` for all active instances."""
        return {wid: sm.state.name for wid, sm in self._instances.items()}

    async def shutdown(self) -> None:
        """Clear all instances."""
        self._instances.clear()
        self._types.clear()

    # ── Internal helpers ──────────────────────────────────────────────

    def _resolve_wtype(self, workflow_id: str, params: dict) -> str | None:
        """Resolve the workflow type name for *workflow_id*.

        Resolution order:
        1. ``params["type"]`` (explicit).
        2. If already registered, return cached type.
        3. Prefix inference from *workflow_id* (e.g. ``rebate-*``).
        """
        if "type" in params:
            return params["type"]
        if workflow_id in self._types:
            return self._types[workflow_id]
        return _infer_workflow_type(workflow_id)

    def _lookup_sm(self, wtype: str) -> tuple[Any, Any] | None:
        """Return ``(state_machine_class, event_enum)`` for *wtype*.

        Checks ``PluginRegistry`` first, then the hardcoded map.
        """
        cls = self._registry.get_workflow(wtype)
        if cls is not None:
            # When registered via PluginRegistry, expect the companion
            # event enum to be available as ``cls.Event``.
            event_enum = getattr(cls, "Event", None)
            if event_enum is not None:
                return cls, event_enum

        entry = WORKFLOW_TYPE_MAP.get(wtype)
        if entry is not None:
            return entry

        return None

    def _event_for_cmd(self, event_enum: type, command: CommandType) -> Any | None:
        """Resolve a :class:`CommandType` to an *event_enum* member."""
        event_name = COMMAND_TO_EVENT.get(command)
        if event_name is not None:
            return getattr(event_enum, event_name, None)

        pair_event = PAIR_COMMAND_MAP.get(command.name)
        if pair_event is not None:
            return getattr(event_enum, pair_event, None)

        return None

    def _handle_start(self, cmd: WorkflowCommand) -> CommandResult:
        """Process a START command — instantiate a new state machine."""
        if cmd.workflow_id in self._instances:
            return _fail(
                cmd,
                f"Workflow '{cmd.workflow_id}' already running",
            )

        wtype = self._resolve_wtype(cmd.workflow_id, cmd.params)
        if wtype is None:
            return _fail(
                cmd,
                f"Cannot determine workflow type for '{cmd.workflow_id}'",
            )

        entry = self._lookup_sm(wtype)
        if entry is None:
            return _fail(cmd, f"Unknown workflow type '{wtype}'")

        sm_cls, event_enum = entry
        start_event = getattr(event_enum, "START", None)
        if start_event is None:
            return _fail(cmd, f"Workflow type '{wtype}' has no START event")

        sm = sm_cls(cmd.workflow_id)
        self._instances[cmd.workflow_id] = sm
        self._types[cmd.workflow_id] = wtype

        try:
            sm.transition(start_event)
        except ValueError as exc:
            del self._instances[cmd.workflow_id]
            del self._types[cmd.workflow_id]
            return _fail(cmd, str(exc))

        return CommandResult(
            workflow_id=cmd.workflow_id,
            command=cmd.command,
            success=True,
            state=sm.state.name,
            instance_count=len(self._instances),
        )

    def _handle_existing(self, cmd: WorkflowCommand) -> CommandResult:
        """Process a command that targets an existing workflow instance."""
        sm = self._instances.get(cmd.workflow_id)
        if sm is None:
            return _fail(cmd, f"Workflow '{cmd.workflow_id}' not found")

        # RESTART = reset() then START
        if cmd.command == CommandType.RESTART:
            return self._handle_restart(cmd, sm)

        previous = sm.state.name

        if sm.is_terminal():
            return CommandResult(
                workflow_id=cmd.workflow_id,
                command=cmd.command,
                success=False,
                state=sm.state.name,
                previous_state=previous,
                message="Workflow is in a terminal state",
                instance_count=len(self._instances),
            )

        event_enum = self._resolve_event_enum(sm)
        if event_enum is None:
            return _fail(
                cmd,
                f"Cannot resolve event enum for {type(sm).__name__}",
            )

        event = self._event_for_cmd(event_enum, cmd.command)
        if event is None:
            return _fail(
                cmd,
                f"Unsupported command {cmd.command.name}",
            )

        try:
            sm.transition(event)
        except ValueError as exc:
            return CommandResult(
                workflow_id=cmd.workflow_id,
                command=cmd.command,
                success=False,
                state=sm.state.name,
                previous_state=previous,
                message=str(exc),
                instance_count=len(self._instances),
            )

        return CommandResult(
            workflow_id=cmd.workflow_id,
            command=cmd.command,
            success=True,
            state=sm.state.name,
            previous_state=previous,
            instance_count=len(self._instances),
        )

    def _handle_restart(self, cmd: WorkflowCommand, sm: Any) -> CommandResult:
        """Reset *sm* then apply START."""
        previous = sm.state.name
        sm.reset()

        event_enum = self._resolve_event_enum(sm)
        if event_enum is None:
            return _fail(cmd, f"Cannot resolve event enum for {type(sm).__name__}")

        start_event = getattr(event_enum, "START", None)
        if start_event is None:
            return _fail(cmd, "State machine has no START event")

        try:
            sm.transition(start_event)
        except ValueError as exc:
            return CommandResult(
                workflow_id=cmd.workflow_id,
                command=cmd.command,
                success=False,
                state=sm.state.name,
                previous_state=previous,
                message=str(exc),
                instance_count=len(self._instances),
            )

        return CommandResult(
            workflow_id=cmd.workflow_id,
            command=cmd.command,
            success=True,
            state=sm.state.name,
            previous_state=previous,
            instance_count=len(self._instances),
        )

    @staticmethod
    def _resolve_event_enum(sm: Any) -> type | None:
        """Find the companion *Event enum for a state machine instance.

        Uses the hardcoded WORKFLOW_TYPE_MAP (reverse-lookup by type)
        as the primary path, with a module-inspection fallback.
        """
        sm_type = type(sm)
        for entry_sm_cls, entry_ev_cls in WORKFLOW_TYPE_MAP.values():
            if sm_type is entry_sm_cls:
                return entry_ev_cls

        # Fallback: inspect the module for a *Event enum
        import sys

        module = sys.modules.get(sm_type.__module__)
        if module is not None:
            for name in dir(module):
                obj = getattr(module, name)
                if isinstance(obj, type) and issubclass(obj, Enum) and name.endswith("Event"):
                    return obj

        return None


def _fail(cmd: WorkflowCommand, message: str) -> CommandResult:
    """Build a failure :class:`CommandResult`."""
    return CommandResult(
        workflow_id=cmd.workflow_id,
        command=cmd.command,
        success=False,
        message=message,
    )
