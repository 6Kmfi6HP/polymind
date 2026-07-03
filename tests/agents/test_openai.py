"""Tests for OpenAIAgent provider."""

from __future__ import annotations

import sys
from unittest.mock import MagicMock

import pytest

from polymind.agents.base import (
    ActionResult,
    AgentConfig,
    AgentRole,
    Decision,
    Observation,
    Reflection,
)
from polymind.agents.openai import OpenAIAgent, create_openai_agent


class TestOpenAIAgentConstruction:
    def test_construct_with_config(self) -> None:
        config = AgentConfig(role=AgentRole.DECIDER, model="gpt-4")
        agent = OpenAIAgent(config=config)
        assert agent.config.role == AgentRole.DECIDER
        assert agent.config.model == "gpt-4"

    def test_construct_with_api_key(self) -> None:
        config = AgentConfig(role=AgentRole.DECIDER)
        agent = OpenAIAgent(config=config, api_key="sk-test-123")
        assert agent._api_key == "sk-test-123"


class TestOpenAIAgentDecide:
    @pytest.mark.asyncio
    async def test_decide_returns_decision(self) -> None:
        """decide() should return a Decision with a non-empty action."""
        mock_choice = MagicMock()
        mock_choice.message.content = "buy 10 shares"

        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response

        agent = OpenAIAgent(
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
        mock_choice = MagicMock()
        mock_choice.message.content = "hold"

        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response

        config = AgentConfig(
            role=AgentRole.DECIDER,
            model="gpt-4-turbo",
            temperature=0.3,
            max_tokens=2048,
        )
        agent = OpenAIAgent(config=config, client=mock_client)

        await agent.decide(Observation(data={"prompt": "test"}))

        mock_client.chat.completions.create.assert_called_once_with(
            model="gpt-4-turbo",
            max_tokens=2048,
            temperature=0.3,
            messages=[{"role": "user", "content": "test"}],
        )

    @pytest.mark.asyncio
    async def test_decide_with_empty_content(self) -> None:
        """decide() should handle empty response content."""
        mock_choice = MagicMock()
        mock_choice.message.content = None

        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response

        agent = OpenAIAgent(
            config=AgentConfig(role=AgentRole.DECIDER),
            client=mock_client,
        )

        result = await agent.decide(Observation(data={"prompt": "test"}))
        assert isinstance(result, Decision)
        assert result.action == ""

    @pytest.mark.asyncio
    async def test_decide_uses_observation_data_as_fallback_prompt(self) -> None:
        """decide() should use str(data) when no 'prompt' key is present."""
        mock_choice = MagicMock()
        mock_choice.message.content = "fallback"

        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response

        agent = OpenAIAgent(
            config=AgentConfig(role=AgentRole.DECIDER),
            client=mock_client,
        )

        result = await agent.decide(Observation(data={"price": 0.5, "spread": 0.01}))
        assert isinstance(result, Decision)
        assert result.action == "fallback"

    @pytest.mark.asyncio
    async def test_decide_lazy_import_on_real_call(self) -> None:
        """decide() should use the injected client, not trigger a real import."""
        mock_choice = MagicMock()
        mock_choice.message.content = "ok"

        mock_response = MagicMock()
        mock_response.choices = [mock_choice]

        mock_client = MagicMock()
        mock_client.chat.completions.create.return_value = mock_response

        agent = OpenAIAgent(
            config=AgentConfig(role=AgentRole.DECIDER),
            client=mock_client,
        )

        result = await agent.decide(Observation(data={"prompt": "x"}))
        assert result.action == "ok"

    @pytest.mark.asyncio
    async def test_decide_without_client_uses_lazy_import(self) -> None:
        """decide() should lazy-import OpenAI when no client is injected."""
        import types

        mock_openai_module = types.ModuleType("openai")
        mock_openai_class = MagicMock()
        mock_openai_module.OpenAI = mock_openai_class

        old_modules = sys.modules.copy()
        sys.modules["openai"] = mock_openai_module

        try:
            mock_instance = MagicMock()
            mock_openai_class.return_value = mock_instance

            mock_choice = MagicMock()
            mock_choice.message.content = "lazy import"
            mock_response = MagicMock()
            mock_response.choices = [mock_choice]
            mock_instance.chat.completions.create.return_value = mock_response

            agent = OpenAIAgent(
                config=AgentConfig(role=AgentRole.DECIDER, model="gpt-4"),
            )

            result = await agent.decide(Observation(data={"prompt": "hello"}))
            assert result.action == "lazy import"
            mock_openai_class.assert_called_once()
        finally:
            sys.modules.update(old_modules)


class TestOpenAIAgentAct:
    @pytest.mark.asyncio
    async def test_act_returns_action_result(self) -> None:
        agent = OpenAIAgent(config=AgentConfig(role=AgentRole.ACTOR))
        result = await agent.act(Decision(action="buy", params={"size": 10}))
        assert isinstance(result, ActionResult)
        assert result.success
        assert result.data["action"] == "buy"
        assert result.data["params"] == {"size": 10}

    @pytest.mark.asyncio
    async def test_act_with_empty_action(self) -> None:
        agent = OpenAIAgent(config=AgentConfig(role=AgentRole.ACTOR))
        result = await agent.act(Decision(action=""))
        assert not result.success
        assert result.error == "No action specified in decision"


class TestOpenAIAgentReflect:
    @pytest.mark.asyncio
    async def test_reflect_on_success(self) -> None:
        agent = OpenAIAgent(config=AgentConfig(role=AgentRole.REFLECTOR))
        result = await agent.reflect(ActionResult(success=True, data={"action": "buy"}))
        assert isinstance(result, Reflection)
        assert "successfully" in result.insight
        assert result.suggested_improvement is None

    @pytest.mark.asyncio
    async def test_reflect_on_failure(self) -> None:
        agent = OpenAIAgent(config=AgentConfig(role=AgentRole.REFLECTOR))
        result = await agent.reflect(ActionResult(success=False, error="timeout"))
        assert isinstance(result, Reflection)
        assert "failed" in result.insight
        assert result.suggested_improvement is not None


class TestCreateOpenAIAgent:
    def test_create_with_defaults(self) -> None:
        agent = create_openai_agent()
        assert isinstance(agent, OpenAIAgent)
        assert agent.config.role == AgentRole.DECIDER
        assert agent.config.model == "gpt-4"
        assert agent.config.temperature == 0.7
        assert agent.config.max_tokens == 4096

    def test_create_with_custom_params(self) -> None:
        agent = create_openai_agent(
            api_key="sk-test",
            model="gpt-4-turbo",
            temperature=0.1,
            max_tokens=1024,
            role="observer",
        )
        assert agent._api_key == "sk-test"
        assert agent.config.role == AgentRole.OBSERVER
        assert agent.config.model == "gpt-4-turbo"
        assert agent.config.temperature == 0.1
        assert agent.config.max_tokens == 1024

    def test_create_with_api_key(self) -> None:
        agent = create_openai_agent(api_key="sk-test-key")
        assert agent._api_key == "sk-test-key"

    def test_create_without_api_key(self) -> None:
        agent = create_openai_agent()
        assert agent._api_key is None
