
"""Base agent abstraction — observe, decide, act, reflect loop."""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum, auto


class AgentRole(Enum):
    OBSERVER = auto()
    DECIDER = auto()
    ACTOR = auto()
    REFLECTOR = auto()


@dataclass
class AgentConfig:
    role: AgentRole
    model: str = "claude-sonnet-4"
    temperature: float = 0.7
    max_tokens: int = 4096


@dataclass
class AgentMessage:
    role: str
    content: str
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class Observation:
    data: dict = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.now)


@dataclass
class Decision:
    action: str
    params: dict = field(default_factory=dict)
    confidence: float = 1.0


@dataclass
class ActionResult:
    success: bool
    data: dict = field(default_factory=dict)
    error: str | None = None


@dataclass
class Reflection:
    insight: str
    suggested_improvement: str | None = None


class BaseAgent(ABC):
    def __init__(self, config: AgentConfig) -> None:
        self.config = config

    async def observe(self, context: dict) -> Observation:
        return Observation(data={})

    @abstractmethod
    async def decide(self, observation: Observation) -> Decision:
        ...

    @abstractmethod
    async def act(self, decision: Decision) -> ActionResult:
        ...

    @abstractmethod
    async def reflect(self, outcome: ActionResult) -> Reflection:
        ...
