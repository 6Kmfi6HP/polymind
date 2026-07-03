"""Tests for IntelligenceAgent."""

from __future__ import annotations

import pytest

from polymind.agents.base import (
    ActionResult,
    AgentConfig,
    AgentRole,
    Decision,
    Observation,
    Reflection,
)
from polymind.agents.intelligence import IntelligenceAgent


class TestIntelligenceAgentConstruction:
    """Construction and configuration."""

    def test_construct_with_config(self) -> None:
        config = AgentConfig(role=AgentRole.DECIDER)
        agent = IntelligenceAgent(config=config)
        assert agent.config.role == AgentRole.DECIDER

    def test_construct_with_default_market_ids(self) -> None:
        config = AgentConfig(role=AgentRole.DECIDER)
        agent = IntelligenceAgent(config=config, market_ids=["0xabc", "0xdef"])
        assert agent._market_ids == ["0xabc", "0xdef"]

    def test_construct_defaults_to_empty_market_ids(self) -> None:
        config = AgentConfig(role=AgentRole.DECIDER)
        agent = IntelligenceAgent(config=config)
        assert agent._market_ids == []


class TestIntelligenceAgentGatherContext:
    """Context-gathering behaviour."""

    @pytest.mark.asyncio
    async def test_gather_context_returns_dict(self) -> None:
        agent = IntelligenceAgent(config=AgentConfig(role=AgentRole.DECIDER))
        context = await agent.gather_context(["0x123", "0x456"])
        assert isinstance(context, dict)

    @pytest.mark.asyncio
    async def test_gather_context_contains_expected_keys(self) -> None:
        agent = IntelligenceAgent(config=AgentConfig(role=AgentRole.DECIDER))
        context = await agent.gather_context(["0x123"])
        assert "market_ids" in context
        assert "news_sentiment" in context
        assert "social_volume" in context
        assert "price_trend" in context
        assert "volume_24h" in context

    @pytest.mark.asyncio
    async def test_gather_context_preserves_market_ids(self) -> None:
        agent = IntelligenceAgent(config=AgentConfig(role=AgentRole.DECIDER))
        market_ids = ["0xabc", "0xdef"]
        context = await agent.gather_context(market_ids)
        assert context["market_ids"] == ["0xabc", "0xdef"]

    @pytest.mark.asyncio
    async def test_gather_context_returns_default_values(self) -> None:
        agent = IntelligenceAgent(config=AgentConfig(role=AgentRole.DECIDER))
        context = await agent.gather_context(["0x123"])
        assert context["news_sentiment"] == 0.0
        assert context["social_volume"] == 0
        assert context["price_trend"] == "neutral"
        assert context["volume_24h"] == 0.0


class TestIntelligenceAgentDecide:
    """Decision-making using gathered context."""

    @pytest.mark.asyncio
    async def test_decide_returns_decision(self) -> None:
        agent = IntelligenceAgent(config=AgentConfig(role=AgentRole.DECIDER))
        observation = Observation(data={"market_ids": ["0x123"]})
        result = await agent.decide(observation)
        assert isinstance(result, Decision)

    @pytest.mark.asyncio
    async def test_decide_uses_market_ids_from_observation(self) -> None:
        agent = IntelligenceAgent(config=AgentConfig(role=AgentRole.DECIDER))
        observation = Observation(data={"market_ids": ["0xabc"]})
        result = await agent.decide(observation)
        assert "0xabc" in result.params.get("market_ids", [])

    @pytest.mark.asyncio
    async def test_decide_falls_back_to_instance_market_ids(self) -> None:
        agent = IntelligenceAgent(
            config=AgentConfig(role=AgentRole.DECIDER),
            market_ids=["0xfallback"],
        )
        observation = Observation(data={})
        result = await agent.decide(observation)
        assert "0xfallback" in result.params.get("market_ids", [])

    @pytest.mark.asyncio
    async def test_decide_uses_unknown_when_no_market_ids_available(self) -> None:
        agent = IntelligenceAgent(config=AgentConfig(role=AgentRole.DECIDER))
        observation = Observation(data={})
        result = await agent.decide(observation)
        assert "unknown" in result.params.get("market_ids", [])

    @pytest.mark.asyncio
    async def test_decide_holds_with_neutral_sentiment(self) -> None:
        agent = IntelligenceAgent(config=AgentConfig(role=AgentRole.DECIDER))
        observation = Observation(data={"market_ids": ["0x123"]})
        result = await agent.decide(observation)
        # Default sentiment is 0.0 -> neutral -> hold
        assert result.action == "hold"
        assert result.confidence == 0.5

    @pytest.mark.asyncio
    async def test_decide_returns_valid_action_string(self) -> None:
        """Verify the agent returns one of the expected actions."""
        agent = IntelligenceAgent(config=AgentConfig(role=AgentRole.DECIDER))
        observation = Observation(data={"market_ids": ["0x123"]})
        result = await agent.decide(observation)
        assert result.action in ("buy", "sell", "hold")

    @pytest.mark.asyncio
    async def test_decide_includes_context_in_params(self) -> None:
        agent = IntelligenceAgent(config=AgentConfig(role=AgentRole.DECIDER))
        observation = Observation(data={"market_ids": ["0x123"]})
        result = await agent.decide(observation)
        assert "context" in result.params
        assert isinstance(result.params["context"], dict)
        assert "market_ids" in result.params["context"]

    @pytest.mark.asyncio
    async def test_decide_confidence_is_float(self) -> None:
        agent = IntelligenceAgent(config=AgentConfig(role=AgentRole.DECIDER))
        observation = Observation(data={"market_ids": ["0x123"]})
        result = await agent.decide(observation)
        assert isinstance(result.confidence, float)
        assert 0 <= result.confidence <= 1.0


class TestIntelligenceAgentAct:
    """Action execution."""

    @pytest.mark.asyncio
    async def test_act_returns_action_result_on_success(self) -> None:
        agent = IntelligenceAgent(config=AgentConfig(role=AgentRole.ACTOR))
        result = await agent.act(Decision(action="buy", params={"size": 10}))
        assert isinstance(result, ActionResult)
        assert result.success
        assert result.data["action"] == "buy"
        assert result.data["params"] == {"size": 10}

    @pytest.mark.asyncio
    async def test_act_with_empty_action_returns_error(self) -> None:
        agent = IntelligenceAgent(config=AgentConfig(role=AgentRole.ACTOR))
        result = await agent.act(Decision(action=""))
        assert not result.success
        assert result.error == "No action specified in decision"


class TestIntelligenceAgentReflect:
    """Reflection behaviour."""

    @pytest.mark.asyncio
    async def test_reflect_on_success(self) -> None:
        agent = IntelligenceAgent(config=AgentConfig(role=AgentRole.REFLECTOR))
        result = await agent.reflect(ActionResult(success=True, data={"action": "buy"}))
        assert isinstance(result, Reflection)
        assert "successfully" in result.insight
        assert result.suggested_improvement is None

    @pytest.mark.asyncio
    async def test_reflect_on_failure(self) -> None:
        agent = IntelligenceAgent(config=AgentConfig(role=AgentRole.REFLECTOR))
        result = await agent.reflect(ActionResult(success=False, error="timeout"))
        assert isinstance(result, Reflection)
        assert "failed" in result.insight
        assert result.suggested_improvement is not None
