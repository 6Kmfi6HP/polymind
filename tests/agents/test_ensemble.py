"""Tests for EnsembleAgent."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest

from polymind.agents.base import (
    ActionResult,
    AgentConfig,
    AgentRole,
    Decision,
    Observation,
    Reflection,
)
from polymind.agents.ensemble import EnsembleAgent, EnsembleStrategy


def _make_mock_agent(action: str = "hold", confidence: float = 0.5) -> MagicMock:
    """Create a mock agent whose async methods return fixed decisions."""
    agent = MagicMock()
    agent.decide = AsyncMock(return_value=Decision(action=action, confidence=confidence))
    agent.act = AsyncMock(return_value=ActionResult(success=True, data={"action": action}))
    agent.reflect = AsyncMock(
        return_value=Reflection(insight="test insight", suggested_improvement=None)
    )
    return agent


class TestEnsembleAgentConstruction:
    """Construction and configuration."""

    def test_construct_with_agents(self) -> None:
        config = AgentConfig(role=AgentRole.DECIDER)
        mock1 = _make_mock_agent()
        mock2 = _make_mock_agent()
        agent = EnsembleAgent(config=config, agents=[mock1, mock2])
        assert len(agent.agents) == 2
        assert agent.strategy == EnsembleStrategy.FIRST_RESPONDER

    def test_construct_with_strategy(self) -> None:
        config = AgentConfig(role=AgentRole.DECIDER)
        mock1 = _make_mock_agent()
        mock2 = _make_mock_agent()
        agent = EnsembleAgent(
            config=config,
            agents=[mock1, mock2],
            strategy=EnsembleStrategy.MAJORITY,
        )
        assert agent.strategy == EnsembleStrategy.MAJORITY

    def test_construct_empty_agents_raises(self) -> None:
        config = AgentConfig(role=AgentRole.DECIDER)
        with pytest.raises(ValueError, match="at least one"):
            EnsembleAgent(config=config, agents=[])

    def test_construct_single_agent(self) -> None:
        config = AgentConfig(role=AgentRole.DECIDER)
        mock = _make_mock_agent()
        agent = EnsembleAgent(config=config, agents=[mock])
        assert len(agent.agents) == 1

    def test_strategy_property(self) -> None:
        config = AgentConfig(role=AgentRole.DECIDER)
        mock = _make_mock_agent()
        agent = EnsembleAgent(
            config=config,
            agents=[mock],
            strategy=EnsembleStrategy.WEIGHTED_VOTE,
        )
        assert agent.strategy == EnsembleStrategy.WEIGHTED_VOTE


class TestEnsembleAgentDecide:
    """Ensemble decision strategies."""

    @pytest.mark.asyncio
    async def test_first_responder_returns_first_agent_decision(self) -> None:
        config = AgentConfig(role=AgentRole.DECIDER)
        agent1 = _make_mock_agent(action="buy", confidence=0.9)
        agent2 = _make_mock_agent(action="sell", confidence=0.8)
        ensemble = EnsembleAgent(
            config=config,
            agents=[agent1, agent2],
            strategy=EnsembleStrategy.FIRST_RESPONDER,
        )

        result = await ensemble.decide(Observation(data={}))
        assert result.action == "buy"

    @pytest.mark.asyncio
    async def test_weighted_vote_returns_highest_confidence(self) -> None:
        config = AgentConfig(role=AgentRole.DECIDER)
        agent1 = _make_mock_agent(action="buy", confidence=0.6)
        agent2 = _make_mock_agent(action="sell", confidence=0.9)
        ensemble = EnsembleAgent(
            config=config,
            agents=[agent1, agent2],
            strategy=EnsembleStrategy.WEIGHTED_VOTE,
        )

        result = await ensemble.decide(Observation(data={}))
        assert result.action == "sell"
        assert result.confidence == 0.9

    @pytest.mark.asyncio
    async def test_majority_returns_most_voted_action(self) -> None:
        config = AgentConfig(role=AgentRole.DECIDER)
        agent1 = _make_mock_agent(action="buy")
        agent2 = _make_mock_agent(action="buy")
        agent3 = _make_mock_agent(action="sell")
        ensemble = EnsembleAgent(
            config=config,
            agents=[agent1, agent2, agent3],
            strategy=EnsembleStrategy.MAJORITY,
        )

        result = await ensemble.decide(Observation(data={}))
        assert result.action == "buy"

    @pytest.mark.asyncio
    async def test_majority_tie_resolves_to_first_encountered(self) -> None:
        """When votes are tied, the first action inserted into the tally wins."""
        config = AgentConfig(role=AgentRole.DECIDER)
        agent1 = _make_mock_agent(action="buy")
        agent2 = _make_mock_agent(action="sell")
        ensemble = EnsembleAgent(
            config=config,
            agents=[agent1, agent2],
            strategy=EnsembleStrategy.MAJORITY,
        )

        result = await ensemble.decide(Observation(data={}))
        # vote_counts = {"buy": 1, "sell": 1} -> max returns "buy" (first inserted)
        assert result.action == "buy"

    @pytest.mark.asyncio
    async def test_decide_runs_all_sub_agents(self) -> None:
        config = AgentConfig(role=AgentRole.DECIDER)
        agent1 = _make_mock_agent()
        agent2 = _make_mock_agent()
        ensemble = EnsembleAgent(
            config=config,
            agents=[agent1, agent2],
            strategy=EnsembleStrategy.FIRST_RESPONDER,
        )

        await ensemble.decide(Observation(data={}))
        agent1.decide.assert_called_once()
        agent2.decide.assert_called_once()

    @pytest.mark.asyncio
    async def test_decide_tags_decision_with_agent_index(self) -> None:
        config = AgentConfig(role=AgentRole.DECIDER)
        agent1 = _make_mock_agent(action="buy")
        agent2 = _make_mock_agent(action="sell")
        ensemble = EnsembleAgent(
            config=config,
            agents=[agent1, agent2],
            strategy=EnsembleStrategy.FIRST_RESPONDER,
        )

        result = await ensemble.decide(Observation(data={}))
        assert result.params.get("_ensemble_agent_index") == 0

    @pytest.mark.asyncio
    async def test_decide_with_single_agent(self) -> None:
        config = AgentConfig(role=AgentRole.DECIDER)
        agent1 = _make_mock_agent(action="buy")
        ensemble = EnsembleAgent(
            config=config,
            agents=[agent1],
        )

        result = await ensemble.decide(Observation(data={}))
        assert result.action == "buy"


class TestEnsembleAgentAct:
    """Action delegation."""

    @pytest.mark.asyncio
    async def test_act_delegates_to_agent_by_index(self) -> None:
        config = AgentConfig(role=AgentRole.ACTOR)
        agent1 = _make_mock_agent()
        agent2 = _make_mock_agent()
        ensemble = EnsembleAgent(
            config=config,
            agents=[agent1, agent2],
            strategy=EnsembleStrategy.FIRST_RESPONDER,
        )

        decision = Decision(action="buy", params={"_ensemble_agent_index": 1})
        result = await ensemble.act(decision)
        assert result.success
        agent2.act.assert_called_once_with(decision)
        agent1.act.assert_not_called()

    @pytest.mark.asyncio
    async def test_act_defaults_to_first_agent_without_index(self) -> None:
        config = AgentConfig(role=AgentRole.ACTOR)
        agent1 = _make_mock_agent()
        agent2 = _make_mock_agent()
        ensemble = EnsembleAgent(
            config=config,
            agents=[agent1, agent2],
        )

        decision = Decision(action="buy")
        result = await ensemble.act(decision)
        assert result.success
        agent1.act.assert_called_once_with(decision)

    @pytest.mark.asyncio
    async def test_act_handles_invalid_agent_index(self) -> None:
        config = AgentConfig(role=AgentRole.ACTOR)
        agent1 = _make_mock_agent()
        ensemble = EnsembleAgent(
            config=config,
            agents=[agent1],
        )

        decision = Decision(action="buy", params={"_ensemble_agent_index": 99})
        result = await ensemble.act(decision)
        assert result.success
        # Falls back to first agent
        agent1.act.assert_called_once_with(decision)


class TestEnsembleAgentReflect:
    """Reflection collection."""

    @pytest.mark.asyncio
    async def test_reflect_returns_first_agent_reflection(self) -> None:
        config = AgentConfig(role=AgentRole.REFLECTOR)
        agent1 = _make_mock_agent()
        agent2 = _make_mock_agent()
        agent2.reflect.return_value = Reflection(
            insight="other insight",
            suggested_improvement="improve",
        )
        ensemble = EnsembleAgent(
            config=config,
            agents=[agent1, agent2],
        )

        result = await ensemble.reflect(ActionResult(success=True, data={"action": "buy"}))
        assert result.insight == "test insight"

    @pytest.mark.asyncio
    async def test_reflect_runs_all_sub_agents(self) -> None:
        config = AgentConfig(role=AgentRole.REFLECTOR)
        agent1 = _make_mock_agent()
        agent2 = _make_mock_agent()
        ensemble = EnsembleAgent(
            config=config,
            agents=[agent1, agent2],
        )

        await ensemble.reflect(ActionResult(success=True, data={"action": "buy"}))
        agent1.reflect.assert_called_once()
        agent2.reflect.assert_called_once()
