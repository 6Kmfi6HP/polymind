"""Tests for AnthropicAgent provider."""

from __future__ import annotations

import sys
from unittest.mock import MagicMock

import pytest

from polymind.agents.anthropic import AnthropicAgent, create_anthropic_agent
from polymind.agents.base import (
    ActionResult,
    AgentConfig,
    AgentRole,
    Decision,
    Observation,
    Reflection,
)


class TestAnthropicAgentConstruction:
    def test_construct_with_config(self) -> None:
        config = AgentConfig(role=AgentRole.DECIDER, model="claude-sonnet-4")
        agent = AnthropicAgent(config=config)
        assert agent.config.role == AgentRole.DECIDER
        assert agent.config.model == "claude-sonnet-4"

    def test_construct_with_api_key(self) -> None:
        config = AgentConfig(role=AgentRole.DECIDER)
        agent = AnthropicAgent(config=config, api_key="sk-test-123")
        assert agent._api_key == "sk-test-123"


class TestAnthropicAgentDecide:
    @pytest.mark.asyncio
    async def test_decide_returns_decision(self) -> None:
        """decide() should return a Decision with a non-empty action."""
        mock_message = MagicMock()
        mock_message.content = [MagicMock(text="buy 10 shares")]

        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_message

        agent = AnthropicAgent(
            config=AgentConfig(role=AgentRole.DECIDER),
            client=mock_client,
        )

        observation = Observation(data={"prompt": "What should I do?"})
        result = await agent.decide(observation)

        assert isinstance(result, Decision)
        assert result.action == "buy 10 shares"
        assert result.confidence == 0.8

    @pytest.mark.asyncio
    async def test_decide_calls_create_with_correct_params(self) -> None:
        """decide() should pass config params to the SDK."""
        mock_message = MagicMock()
        mock_message.content = [MagicMock(text="hold")]

        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_message

        config = AgentConfig(
            role=AgentRole.DECIDER,
            model="claude-opus-4",
            temperature=0.3,
            max_tokens=2048,
        )
        agent = AnthropicAgent(config=config, client=mock_client)

        await agent.decide(Observation(data={"prompt": "test"}))

        mock_client.messages.create.assert_called_once_with(
            model="claude-opus-4",
            max_tokens=2048,
            temperature=0.3,
            messages=[{"role": "user", "content": "test"}],
        )

    @pytest.mark.asyncio
    async def test_decide_with_empty_content(self) -> None:
        """decide() should handle empty response content."""
        mock_message = MagicMock()
        mock_message.content = []

        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_message

        agent = AnthropicAgent(
            config=AgentConfig(role=AgentRole.DECIDER),
            client=mock_client,
        )

        result = await agent.decide(Observation(data={"prompt": "test"}))
        assert isinstance(result, Decision)
        assert result.action == ""

    @pytest.mark.asyncio
    async def test_decide_uses_observation_data_as_fallback_prompt(self) -> None:
        """decide() should use str(data) when no 'prompt' key is present."""
        mock_message = MagicMock()
        mock_message.content = [MagicMock(text="fallback")]

        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_message

        agent = AnthropicAgent(
            config=AgentConfig(role=AgentRole.DECIDER),
            client=mock_client,
        )

        result = await agent.decide(Observation(data={"price": 0.5, "spread": 0.01}))
        assert isinstance(result, Decision)
        assert result.action == "fallback"

    @pytest.mark.asyncio
    async def test_decide_lazy_import_on_real_call(self) -> None:
        """decide() should use the injected client, not trigger a real import."""
        mock_message = MagicMock()
        mock_message.content = [MagicMock(text="ok")]

        mock_client = MagicMock()
        mock_client.messages.create.return_value = mock_message

        agent = AnthropicAgent(
            config=AgentConfig(role=AgentRole.DECIDER),
            client=mock_client,
        )

        result = await agent.decide(Observation(data={"prompt": "x"}))
        assert result.action == "ok"

    @pytest.mark.asyncio
    async def test_decide_without_client_uses_lazy_import(self) -> None:
        """decide() should lazy-import Anthropic when no client is injected."""
        import types

        mock_anthropic_module = types.ModuleType("anthropic")
        mock_anthropic_class = MagicMock()
        mock_anthropic_module.Anthropic = mock_anthropic_class

        old_modules = sys.modules.copy()
        sys.modules["anthropic"] = mock_anthropic_module

        try:
            mock_instance = MagicMock()
            mock_anthropic_class.return_value = mock_instance

            mock_message = MagicMock()
            mock_message.content = [MagicMock(text="lazy import")]
            mock_instance.messages.create.return_value = mock_message

            # Clear cached client so the lazy import path is hit
            agent = AnthropicAgent(
                config=AgentConfig(role=AgentRole.DECIDER, model="claude-sonnet-4"),
            )

            result = await agent.decide(Observation(data={"prompt": "hello"}))
            assert result.action == "lazy import"
            mock_anthropic_class.assert_called_once()
        finally:
            sys.modules.update(old_modules)


class TestAnthropicAgentAct:
    @pytest.mark.asyncio
    async def test_act_returns_action_result(self) -> None:
        agent = AnthropicAgent(config=AgentConfig(role=AgentRole.ACTOR))
        result = await agent.act(Decision(action="buy", params={"size": 10}))
        assert isinstance(result, ActionResult)
        assert result.success
        assert result.data["action"] == "buy"
        assert result.data["params"] == {"size": 10}

    @pytest.mark.asyncio
    async def test_act_with_empty_action(self) -> None:
        agent = AnthropicAgent(config=AgentConfig(role=AgentRole.ACTOR))
        result = await agent.act(Decision(action=""))
        assert not result.success
        assert result.error == "No action specified in decision"


class TestAnthropicAgentReflect:
    @pytest.mark.asyncio
    async def test_reflect_on_success(self) -> None:
        agent = AnthropicAgent(config=AgentConfig(role=AgentRole.REFLECTOR))
        result = await agent.reflect(ActionResult(success=True, data={"action": "buy"}))
        assert isinstance(result, Reflection)
        assert "successfully" in result.insight
        assert result.suggested_improvement is None

    @pytest.mark.asyncio
    async def test_reflect_on_failure(self) -> None:
        agent = AnthropicAgent(config=AgentConfig(role=AgentRole.REFLECTOR))
        result = await agent.reflect(ActionResult(success=False, error="timeout"))
        assert isinstance(result, Reflection)
        assert "failed" in result.insight
        assert result.suggested_improvement is not None


class TestCreateAnthropicAgent:
    def test_create_with_defaults(self) -> None:
        agent = create_anthropic_agent()
        assert isinstance(agent, AnthropicAgent)
        assert agent.config.role == AgentRole.DECIDER
        assert agent.config.model == "claude-sonnet-4"
        assert agent.config.temperature == 0.7
        assert agent.config.max_tokens == 4096

    def test_create_with_custom_params(self) -> None:
        agent = create_anthropic_agent(
            api_key="sk-test",
            model="claude-opus-4",
            temperature=0.1,
            max_tokens=1024,
            role="observer",
        )
        assert agent._api_key == "sk-test"
        assert agent.config.role == AgentRole.OBSERVER
        assert agent.config.model == "claude-opus-4"
        assert agent.config.temperature == 0.1
        assert agent.config.max_tokens == 1024

    def test_create_with_api_key(self) -> None:
        agent = create_anthropic_agent(api_key="sk-test-key")
        assert agent._api_key == "sk-test-key"

    def test_create_without_api_key(self) -> None:
        agent = create_anthropic_agent()
        assert agent._api_key is None
