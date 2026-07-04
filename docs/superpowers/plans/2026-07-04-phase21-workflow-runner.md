# Phase 21: WorkflowRunner Engine — Implementation Plan

---

### Task 1: Create WorkflowRunner class

**File:** `polymind/workflows/runner.py`

New module implementing `WorkflowRunner` with:

1. Import all four state machines: `RebateStateMachine`, `EventMMStateMachine`,
   `CopyTradeStateMachine`, `SniperStateMachine`.

2. `WORKFLOW_TYPE_MAP` — dict mapping string type names to state machine classes:
   `"maker_rebate" -> RebateStateMachine`, `"event_mm" -> EventMMStateMachine`,
   `"copy_trade" -> CopyTradeStateMachine`, `"sniper" -> SniperStateMachine`.

3. `COMMAND_TO_EVENT_MAP` — dict mapping `CommandType` to the common event name
   string (e.g. `CommandType.START -> "START"`, `CommandType.STOP -> "HALT"`,
   `CommandType.PAUSE -> "HALT"`, `CommandType.RESUME -> "RESUME"`).
   Pair commands (`SPLIT`, `MERGE`, `REDEEM`, `SELL_REMAINDER`, `ONE_SIDED_HALT`)
   are mapped by a separate `PAIR_COMMANDS` set and handled via `handle_pair_command`.

4. `CommandResult` dataclass with: `workflow_id`, `command`, `success`, `state`,
   `previous_state`, `message`, `instance_count`.

5. `WorkflowRunner` class:

   - `__init__(self, registry=None)`
     - `self._instances: dict[str, StateMachineProtocol]`
     - `self._types: dict[str, str]` — maps workflow_id -> type_name
     - `self._registry = registry or PluginRegistry()`

   - `process_command(cmd: WorkflowCommand) -> CommandResult`:
     1. Extract `workflow_type` from `cmd.params.get("type")` (or infer from
        naming prefix: `rebate-*`, `event_mm-*`, `copy_trade-*`, `sniper-*`).
     2. For `START`: instantiate the correct state machine, store in `_instances`.
        Reject if `workflow_id` already exists.
     3. For `STOP`, `PAUSE`, `RESUME`, `RESTART`: look up existing instance.
        `RESTART` does `reset()` then `transition(START)`.
     4. For `SPLIT`, `MERGE`, `REDEEM`, `SELL_REMAINDER`, `ONE_SIDED_HALT`:
        look up existing instance, call `handle_pair_command`.
     5. For any command: catch `ValueError` from state machine and return
        `CommandResult(success=False)`.
     6. Return `CommandResult` with updated state info.

   - `get_instance(workflow_id) -> StateMachineProtocol | None`
   - `list_instances() -> dict[str, str]` — current state name per workflow_id
   - `async shutdown()` — clear all state

6. Update `polymind/workflows/__init__.py`:
   - Add `from polymind.workflows.runner import WorkflowRunner, CommandResult`

### Task 2: Create unit tests

**File:** `tests/workflows/test_runner.py`

Test class covering:

1. `test_initial_state` — empty runner, no instances
2. `test_start_workflow` — start each workflow type, verify state == non-IDLE
3. `test_start_duplicate` — start same workflow_id twice, second fails
4. `test_stop_workflow` — start then STOP (HALT), verify HALTED state
5. `test_pause_resume` — start then PAUSE (HALT), then RESUME, back to IDLE
6. `test_restart` — start, STOP, RESTART, verify active again
7. `test_invalid_workflow_type` — unknown type in params, expect failure
8. `test_rebate_lifecycle_start_to_awaiting` — start, ORDERS_PLACED, AWAITING_FILLS
9. `test_get_instance` — get back the state machine, check state
10. `test_list_instances` — multiple workflows, list returns all
11. `test_shutdown` — shutdown clears instances
12. `test_passthrough_invalid_transition` — command that causes invalid transition
13. `test_command_on_nonexistent` — command on unknown workflow_id
14. `test_command_on_terminal` — command on COMPLETED/FAILED workflow
15. `test_event_mm_start` — start event_mm, verify WATCHING state
16. `test_copy_trade_start` — start copy_trade, verify MONITORING state
17. `test_sniper_start` — start sniper, verify WATCHING state
18. `test_workflow_type_inference` — infer from workflow_id prefix `rebate-*` etc.

### Task 3: Wire into workflows/__init__.py

**File:** `polymind/workflows/__init__.py`

- Add `from polymind.workflows.runner import WorkflowRunner, CommandResult`
- Update `__all__`

**File:** `polymind/core/plugin.py` (optional update)

- No changes needed — `PluginRegistry` already has `register_workflow` / `get_workflow`.

### Task 4: Create integration test

**File:** `tests/workflows/test_runner_integration.py`

Integration test that:

1. Registers a workflow type in `PluginRegistry`
2. Creates a `WorkflowRunner` with that registry
3. Starts a workflow via command
4. Verifies the registry + runner work together

### Task 5: Run full test suite

- Run `python -m pytest tests/workflows/ -v` (or equivalent `pytest` binary)
- Run `python -m pytest tests/ -x --timeout=30` to verify no regressions
