"""Tests for BaseAgent."""

from __future__ import annotations

import pytest

from polymind.agents.base import (
    AgentRole, AgentConfig, AgentMessage, BaseAgent,
    Observation, Decision, ActionResult, Reflection,
)


class TestAgentRole:
    def test_values(self) -> None:
        assert isinstance(AgentRole.OBSERVER, AgentRole)
        assert isinstance(AgentRole.REFLECTOR, AgentRole)


class TestAgentConfig:
    def test_defaults(self) -> None:
        c = AgentConfig(role=AgentRole.OBSERVER)
        assert c.model == "claude-sonnet-4"
        assert c.temperature == 0.7
        assert c.max_tokens == 4096


class TestAgentMessage:
    def test_construction(self) -> None:
        m = AgentMessage(role="user", content="hello")
        assert m.role == "user"
        assert m.content == "hello"


class TestObservation:
    def test_construction(self) -> None:
        o = Observation(data={"price": 0.5})
        assert o.data["price"] == 0.5


class TestDecision:
    def test_construction(self) -> None:
        d = Decision(action="buy", params={"size": 10})
        assert d.action == "buy"
        assert d.confidence == 1.0


class TestActionResult:
    def test_success(self) -> None:
        r = ActionResult(success=True)
        assert r.success

    def test_failure(self) -> None:
        r = ActionResult(success=False, error="timeout")
        assert not r.success
        assert r.error == "timeout"


class TestReflection:
    def test_construction(self) -> None:
        r = Reflection(insight="good signal")
        assert r.insight == "good signal"


class TestConcreteAgent:
    class SimpleAgent(BaseAgent):
        async def observe(self, ctx): return Observation(data=ctx)
        async def decide(self, o): return Decision(action="hold")
        async def act(self, d): return ActionResult(success=True)
        async def reflect(self, r): return Reflection(insight="done")

    @pytest.mark.asyncio
    async def test_observe_returns_observation(self) -> None:
        a = self.SimpleAgent(AgentConfig(role=AgentRole.OBSERVER))
        o = await a.observe({"price": 1.0})
        assert isinstance(o, Observation)
        assert o.data["price"] == 1.0

    @pytest.mark.asyncio
    async def test_decide_returns_decision(self) -> None:
        a = self.SimpleAgent(AgentConfig(role=AgentRole.DECIDER))
        d = await a.decide(Observation())
        assert isinstance(d, Decision)
        assert d.action == "hold"

    @pytest.mark.asyncio
    async def test_act_returns_result(self) -> None:
        a = self.SimpleAgent(AgentConfig(role=AgentRole.ACTOR))
        r = await a.act(Decision(action="buy"))
        assert isinstance(r, ActionResult)
        assert r.success

    @pytest.mark.asyncio
    async def test_reflect_returns_reflection(self) -> None:
        a = self.SimpleAgent(AgentConfig(role=AgentRole.REFLECTOR))
        r = await a.reflect(ActionResult(success=True))
        assert isinstance(r, Reflection)
        assert r.insight == "done"
