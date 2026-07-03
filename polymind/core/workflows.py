"""
Workflow command contracts (Phase 2).

WorkflowCommand represents a lifecycle or pair-management command for a
workflow instance.  The workflow runtime interprets the command and
translates it into lower-level intents.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from enum import Enum, auto
from typing import Any, Dict


class CommandType(Enum):
    """Category of a workflow command."""

    # Lifecycle
    START = auto()
    STOP = auto()
    PAUSE = auto()
    RESUME = auto()
    RESTART = auto()

    # Pair lifecycle (for Maker Rebate, Event MM etc.)
    SPLIT = auto()
    MERGE = auto()
    REDEEM = auto()
    SELL_REMAINDER = auto()
    ONE_SIDED_HALT = auto()


@dataclass
class WorkflowCommand:
    """A workflow lifecycle or pair-management command."""

    workflow_id: str
    command: CommandType
    reason: str = ""
    params: Dict[str, Any] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=lambda: datetime.now(timezone.utc))
