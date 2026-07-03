"""Anthropic Claude agent provider — observe, decide, act, reflect loop."""

from __future__ import annotations

from typing import Any

from polymind.agents.base import (
    ActionResult,
    AgentConfig,
    BaseAgent,
    Decision,
    Observation,
    Reflection,
)


class AnthropicAgent(BaseAgent):
    """Agent that uses Anthropic's Claude API for decision-making.

    Uses lazy imports for the Anthropic SDK so the dependency is optional.
    """

    def __init__(
        self,
        config: AgentConfig,
        api_key: str | None = None,
        client: Any = None,
    ) -> None:
        super().__init__(config)
        self._api_key = api_key
        self._client = client

    def _get_client(self) -> Any:
        """Lazy-init and return the Anthropic client."""
        if self._client is not None:
            return self._client

        from anthropic import Anthropic  # type: ignore[import-untyped]

        kwargs: dict[str, Any] = {}
        if self._api_key is not None:
            kwargs["api_key"] = self._api_key
        self._client = Anthropic(**kwargs)
        return self._client

    async def decide(self, observation: Observation) -> Decision:
        """Call Claude to decide on an action based on the observation."""
        client = self._get_client()

        prompt = observation.data.get("prompt", str(observation.data))

        message = client.messages.create(
            model=self.config.model,
            max_tokens=self.config.max_tokens,
            temperature=self.config.temperature,
            messages=[
                {"role": "user", "content": prompt},
            ],
        )

        content = message.content[0].text if message.content else ""

        return Decision(
            action=content.strip(),
            params={"model": self.config.model},
            confidence=0.8,
        )

    async def act(self, decision: Decision) -> ActionResult:
        """Execute the decision and return the result."""
        if not decision.action:
            return ActionResult(
                success=False,
                data={"action": ""},
                error="No action specified in decision",
            )

        return ActionResult(
            success=True,
            data={
                "action": decision.action,
                "params": decision.params,
            },
        )

    async def reflect(self, outcome: ActionResult) -> Reflection:
        """Reflect on the outcome and produce an insight."""
        if outcome.success:
            insight = f"Action completed successfully: {outcome.data.get('action', 'unknown')}"
            suggested_improvement = None
        else:
            insight = f"Action failed: {outcome.error or 'unknown error'}"
            suggested_improvement = "Review the error and adjust the decision parameters"

        return Reflection(
            insight=insight,
            suggested_improvement=suggested_improvement,
        )


def create_anthropic_agent(
    api_key: str | None = None,
    model: str = "claude-sonnet-4",
    temperature: float = 0.7,
    max_tokens: int = 4096,
    role: str | None = None,
) -> AnthropicAgent:
    """Factory to create a configured AnthropicAgent.

    Parameters
    ----------
    api_key : str, optional
        Anthropic API key. If None, falls back to ANTHROPIC_API_KEY env var.
    model : str
        Claude model identifier (default "claude-sonnet-4").
    temperature : float
        Response temperature (default 0.7).
    max_tokens : int
        Maximum output tokens (default 4096).
    role : str, optional
        Agent role string, mapped to AgentRole enum. Defaults to DECIDER.

    Returns
    -------
    AnthropicAgent
        A fully configured agent instance.
    """
    from polymind.agents.base import AgentRole

    role_map: dict[str, AgentRole] = {
        "observer": AgentRole.OBSERVER,
        "decider": AgentRole.DECIDER,
        "actor": AgentRole.ACTOR,
        "reflector": AgentRole.REFLECTOR,
    }

    resolved_role = role_map.get(role.lower() if role else "", AgentRole.DECIDER)

    config = AgentConfig(
        role=resolved_role,
        model=model,
        temperature=temperature,
        max_tokens=max_tokens,
    )

    return AnthropicAgent(config=config, api_key=api_key)
