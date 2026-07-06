> **Status:** Superseded by [`docs/architecture.md`](../../architecture.md) and [`docs/architecture/decisions/`](../../architecture/decisions/). This spec was a design document and is kept for historical reference only.

# Phase 21: WorkflowRunner Engine — Design

**Status:** Design
**Date:** 2026-07-04

## Overview

A `WorkflowRunner` that owns active workflow state machine instances and routes
`WorkflowCommand` (START / STOP / PAUSE / RESUME / SPLIT / MERGE / REDEEM) to the
correct state machine type — `RebateStateMachine`, `EventMMStateMachine`,
`CopyTradeStateMachine`, or `SniperStateMachine`.

The runner follows the `PaperExecutor` pattern: a single class with a registry of
active instances, an async `process_command` entry point, and `async shutdown` for
clean teardown.

## Existing contracts

### `polymind/core/workflows.py` — `WorkflowCommand`, `CommandType`

```
WorkflowCommand:
  workflow_id: str
  command: CommandType
  reason: str = ""
  params: dict[str, Any]
  timestamp: datetime

CommandType:
  START, STOP, PAUSE, RESUME, RESTART   (lifecycle)
  SPLIT, MERGE, REDEEM, SELL_REMAINDER, ONE_SIDED_HALT  (pair lifecycle)
```

### Existing state machines (all follow the same protocol)

| Module | Class | State Enum | Event Enum |
|---|---|---|---|
| `maker_rebate` | `RebateStateMachine` | `RebateState` | `RebateEvent` |
| `event_mm` | `EventMMStateMachine` | `EventMMState` | `EventMMEvent` |
| `copy_trade` | `CopyTradeStateMachine` | `CopyTradeState` | `CopyTradeEvent` |
| `sniper` | `SniperStateMachine` | `SniperState` | `SniperEvent` |

Every state machine exposes:
- `__init__(workflow_id: str)`
- `transition(event) -> StateEnum` — raises `ValueError` on invalid transition
- `can_transition(event) -> bool`
- `is_terminal() -> bool`
- `is_active() -> bool`
- `reset()` — back to IDLE
- `state`, `workflow_id`, `history`, `created_at`, `updated_at`

### `polymind/core/plugin.py` — `PluginRegistry`

Singleton registry with `register_workflow(name, cls_type)` / `get_workflow(name)`.
Workflow types should be registered here so the runner can look up the correct
state machine class by workflow type name.

## Design

### 1. Command-to-event mapping

A static mapping from `CommandType` to each state machine's event enum value.
Shared lifecycle commands (START, STOP, PAUSE, RESUME) map identically across all
machines. Pair lifecycle commands (SPLIT, MERGE, REDEEM, SELL_REMAINDER,
ONE_SIDED_HALT) are workflow-type-specific — the runner delegates them to a
`pair_lifecycle` dispatch that validates the workflow type supports the command.

| CommandType | Mapped Event | Notes |
|---|---|---|
| START | `{Type}Event.START` | All machines define START |
| STOP | `{Type}Event.HALT` | Graceful halt |
| PAUSE | `{Type}Event.HALT` | Same transition as STOP |
| RESUME | `{Type}Event.RESUME` | HALTED -> IDLE |
| RESTART | `reset()` then `START` | Reset state, then start |
| SPLIT | Pair lifecycle | Only Rebate supports (MERGE_DONE event) |
| MERGE | Pair lifecycle | Only Rebate supports (MERGE_DONE event) |
| REDEEM | Pair lifecycle | Rebate + Event MM + Sniper support |
| SELL_REMAINDER | Pair lifecycle | All machines with positions |
| ONE_SIDED_HALT | Special | Halts one side of a pair |

### 2. WorkflowRunner class

Location: `polymind/workflows/runner.py`

```python
class WorkflowRunner:
    """Registry of active workflow instances and command router."""

    def __init__(self, registry: PluginRegistry | None = None):
        self._instances: dict[str, StateMachineProtocol] = {}
        self._types: dict[str, str] = {}  # workflow_id -> type_name
        self._registry = registry or PluginRegistry()

    async def process_command(self, cmd: WorkflowCommand) -> CommandResult:
        """Route a WorkflowCommand to the correct state machine."""

    def get_instance(self, workflow_id: str) -> StateMachineProtocol | None:
        """Return the active state machine instance, if any."""

    def list_instances(self) -> dict[str, str]:
        """Return {workflow_id: state_name} for all active instances."""

    async def shutdown(self) -> None:
        """Clear all instances."""
```

### 3. CommandResult

```python
@dataclass
class CommandResult:
    workflow_id: str
    command: CommandType
    success: bool
    state: str          # current state name after processing
    previous_state: str # state before the command
    message: str = ""
    instance_count: int = 0
```

### 4. Workflow type resolution

The runner needs to know which state machine class to instantiate for a given
workflow. Resolution order:

1. **PluginRegistry lookup** — `self._registry.get_workflow(workflow_type)`
   where `workflow_type` is extracted from the command's `params["type"]` or
   inferred from a naming convention on `workflow_id` (e.g. `rebate-*` prefix).

2. **Direct mapping fallback** — hardcoded map of known workflow type names:
   `"maker_rebate" -> RebateStateMachine`, `"event_mm" -> EventMMStateMachine`,
   `"copy_trade" -> CopyTradeStateMachine`, `"sniper" -> SniperStateMachine`.

### 5. Integration with PaperExecutor

The `WorkflowRunner` does **not** directly execute orders. It accepts commands,
validates them against the state machine, transitions state, and returns the
result. Actual order execution (placing/canceling orders) is handled downstream by
the `PaperExecutor` / `LiveExecutor` after the workflow runner determines the
workflow is in the correct state to proceed.

## Error handling

- Invalid `workflow_id` → `CommandResult(success=False, message="not found")`
- Invalid transition (ValueError from state machine) → `CommandResult(success=False, message=...)`
- Unknown workflow type → `CommandResult(success=False, message="unknown type")`
- Command on terminal workflow → `CommandResult(success=False, message="terminal")`
- Duplicate START → `CommandResult(success=False, message="already running")`
