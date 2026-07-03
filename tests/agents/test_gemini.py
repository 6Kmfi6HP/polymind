"""Tests for GeminiAgent provider."""

from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

import pytest

from polymind.agents.base import (
    ActionResult,
    AgentConfig,
    AgentRole,
    Decision,
    Observation,
    Reflection,
)
from polymind.agents.gemini import GeminiAgent, create_gemini_agent


@pytest.fixture(autouse=True)
def _mock_google_genai():
    """Mock google.genai module for all tests to avoid real imports."""
    mock_types = MagicMock()
    mock_types.GenerateContentConfig = MagicMock()

    mock_genai = MagicMock()
    mock_genai.types = mock_types
    mock_genai.Client = MagicMock()

    google_pkg = MagicMock()
    google_pkg.genai = mock_genai

    with patch.dict(
        sys.modules,
        {
            "google": google_pkg,
            "google.genai": mock_genai,
        },
    ):
        yield


class TestGeminiAgentConstruction:
    def test_construct_with_config(self) -> None:
        config = AgentConfig(role=AgentRole.DECIDER, model="gemini-2.0-flash")
        agent = GeminiAgent(config=config)
        assert agent.config.role == AgentRole.DECIDER
        assert agent.config.model == "gemini-2.0-flash"

    def test_construct_with_api_key(self) -> None:
        config = AgentConfig(role=AgentRole.DECIDER)
        agent = GeminiAgent(config=config, api_key="ai-test-123")
        assert agent._api_key == "ai-test-123"


class TestGeminiAgentDecide:
    @pytest.mark.asyncio
    async def test_decide_returns_decision(self) -> None:
        """decide() should return a Decision with a non-empty action."""
        mock_response = MagicMock()
        mock_response.text = "buy 10 shares"

        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = mock_response

        agent = GeminiAgent(
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
        mock_response = MagicMock()
        mock_response.text = "hold"

        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = mock_response

        config = AgentConfig(
            role=AgentRole.DECIDER,
            model="gemini-2.0-flash",
            temperature=0.3,
            max_tokens=2048,
        )
        agent = GeminiAgent(config=config, client=mock_client)

        await agent.decide(Observation(data={"prompt": "test"}))

        # Verify GenerateContentConfig was constructed with the right params
        call_args = mock_client.models.generate_content.call_args
        assert call_args is not None
        assert call_args[1]["model"] == "gemini-2.0-flash"
        assert call_args[1]["contents"] == "test"

    @pytest.mark.asyncio
    async def test_decide_with_empty_content(self) -> None:
        """decide() should handle empty response content."""
        mock_response = MagicMock()
        mock_response.text = ""

        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = mock_response

        agent = GeminiAgent(
            config=AgentConfig(role=AgentRole.DECIDER),
            client=mock_client,
        )

        result = await agent.decide(Observation(data={"prompt": "test"}))
        assert isinstance(result, Decision)
        assert result.action == ""

    @pytest.mark.asyncio
    async def test_decide_with_none_text(self) -> None:
        """decide() should handle response with None text."""
        mock_response = MagicMock()
        mock_response.text = None

        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = mock_response

        agent = GeminiAgent(
            config=AgentConfig(role=AgentRole.DECIDER),
            client=mock_client,
        )

        result = await agent.decide(Observation(data={"prompt": "test"}))
        assert isinstance(result, Decision)
        assert result.action == ""

    @pytest.mark.asyncio
    async def test_decide_uses_observation_data_as_fallback_prompt(self) -> None:
        """decide() should use str(data) when no 'prompt' key is present."""
        mock_response = MagicMock()
        mock_response.text = "fallback"

        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = mock_response

        agent = GeminiAgent(
            config=AgentConfig(role=AgentRole.DECIDER),
            client=mock_client,
        )

        result = await agent.decide(Observation(data={"price": 0.5, "spread": 0.01}))
        assert isinstance(result, Decision)
        assert result.action == "fallback"

    @pytest.mark.asyncio
    async def test_decide_lazy_import_on_real_call(self) -> None:
        """decide() should use the injected client, not trigger a real import."""
        mock_response = MagicMock()
        mock_response.text = "ok"

        mock_client = MagicMock()
        mock_client.models.generate_content.return_value = mock_response

        agent = GeminiAgent(
            config=AgentConfig(role=AgentRole.DECIDER),
            client=mock_client,
        )

        result = await agent.decide(Observation(data={"prompt": "x"}))
        assert result.action == "ok"

    @pytest.mark.asyncio
    async def test_decide_without_client_uses_lazy_import(self) -> None:
        """decide() should lazy-import google.genai when no client is injected."""
        import types as py_types

        mock_genai_module = py_types.ModuleType("google.genai")
        mock_client_class = MagicMock()
        mock_genai_module.Client = mock_client_class
        mock_types = MagicMock()
        mock_types.GenerateContentConfig = MagicMock()
        mock_genai_module.types = mock_types

        # Build a mock google package
        mock_google = py_types.ModuleType("google")
        mock_google.genai = mock_genai_module

        old_modules = sys.modules.copy()
        sys.modules["google"] = mock_google
        sys.modules["google.genai"] = mock_genai_module

        try:
            mock_instance = MagicMock()
            mock_client_class.return_value = mock_instance

            mock_response = MagicMock()
            mock_response.text = "lazy import"
            mock_instance.models.generate_content.return_value = mock_response

            agent = GeminiAgent(
                config=AgentConfig(role=AgentRole.DECIDER, model="gemini-2.0-flash"),
            )

            result = await agent.decide(Observation(data={"prompt": "hello"}))
            assert result.action == "lazy import"
            mock_client_class.assert_called_once()
        finally:
            sys.modules.update(old_modules)


class TestGeminiAgentAct:
    @pytest.mark.asyncio
    async def test_act_returns_action_result(self) -> None:
        agent = GeminiAgent(config=AgentConfig(role=AgentRole.ACTOR))
        result = await agent.act(Decision(action="buy", params={"size": 10}))
        assert isinstance(result, ActionResult)
        assert result.success
        assert result.data["action"] == "buy"
        assert result.data["params"] == {"size": 10}

    @pytest.mark.asyncio
    async def test_act_with_empty_action(self) -> None:
        agent = GeminiAgent(config=AgentConfig(role=AgentRole.ACTOR))
        result = await agent.act(Decision(action=""))
        assert not result.success
        assert result.error == "No action specified in decision"


class TestGeminiAgentReflect:
    @pytest.mark.asyncio
    async def test_reflect_on_success(self) -> None:
        agent = GeminiAgent(config=AgentConfig(role=AgentRole.REFLECTOR))
        result = await agent.reflect(ActionResult(success=True, data={"action": "buy"}))
        assert isinstance(result, Reflection)
        assert "successfully" in result.insight
        assert result.suggested_improvement is None

    @pytest.mark.asyncio
    async def test_reflect_on_failure(self) -> None:
        agent = GeminiAgent(config=AgentConfig(role=AgentRole.REFLECTOR))
        result = await agent.reflect(ActionResult(success=False, error="timeout"))
        assert isinstance(result, Reflection)
        assert "failed" in result.insight
        assert result.suggested_improvement is not None


class TestCreateGeminiAgent:
    def test_create_with_defaults(self) -> None:
        agent = create_gemini_agent()
        assert isinstance(agent, GeminiAgent)
        assert agent.config.role == AgentRole.DECIDER
        assert agent.config.model == "gemini-2.0-flash"
        assert agent.config.temperature == 0.7
        assert agent.config.max_tokens == 4096

    def test_create_with_custom_params(self) -> None:
        agent = create_gemini_agent(
            api_key="ai-test",
            model="gemini-2.0-pro",
            temperature=0.1,
            max_tokens=1024,
            role="observer",
        )
        assert agent._api_key == "ai-test"
        assert agent.config.role == AgentRole.OBSERVER
        assert agent.config.model == "gemini-2.0-pro"
        assert agent.config.temperature == 0.1
        assert agent.config.max_tokens == 1024

    def test_create_with_api_key(self) -> None:
        agent = create_gemini_agent(api_key="ai-test-key")
        assert agent._api_key == "ai-test-key"

    def test_create_without_api_key(self) -> None:
        agent = create_gemini_agent()
        assert agent._api_key is None
