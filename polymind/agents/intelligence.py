"""Intelligence agent — provides market/sentiment context for decisions."""

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


class IntelligenceAgent(BaseAgent):
    """Enriches strategy prompts with market context and news sentiment.

    Gathers news, social sentiment, and market data to inform decisions.
    The ``gather_context`` method is a stub that returns well-defined default
    values; a production deployment would call external news / sentiment /
    market APIs.

    Parameters
    ----------
    config : AgentConfig
        Agent configuration.
    market_ids : list[str], optional
        Default market identifiers to use when the observation does not
        supply any.
    """

    def __init__(
        self,
        config: AgentConfig,
        market_ids: list[str] | None = None,
    ) -> None:
        super().__init__(config)
        self._market_ids = market_ids or []

    async def gather_context(self, market_ids: list[str]) -> dict[str, Any]:
        """Fetch news, social sentiment, market data for given markets.

        Parameters
        ----------
        market_ids : list[str]
            Identifiers of the markets to gather context for.

        Returns
        -------
        dict
            A dictionary with keys ``market_ids``, ``news_sentiment``,
            ``social_volume``, ``price_trend``, and ``volume_24h``.
        """
        return {
            "market_ids": list(market_ids),
            "news_sentiment": 0.0,
            "social_volume": 0,
            "price_trend": "neutral",
            "volume_24h": 0.0,
        }

    async def decide(self, observation: Observation) -> Decision:
        """Use gathered context to inform a decision.

        Extracts market identifiers from the observation, gathers context
        about each market, then produces a buy/sell/hold decision based on
        aggregate news sentiment.

        Parameters
        ----------
        observation : Observation
            May include ``market_ids`` in ``observation.data``. Falls back to
            instance-level ``market_ids`` or ``["unknown"]``.

        Returns
        -------
        Decision
            A decision whose action is one of ``"buy"`` / ``"sell"`` / ``"hold"``
            and whose ``params`` include the gathered context.
        """
        market_ids: list[str] = observation.data.get("market_ids", self._market_ids)  # type: ignore[assignment]
        if not market_ids:
            market_ids = ["unknown"]

        context = await self.gather_context(market_ids)

        sentiment: float = context.get("news_sentiment", 0.0)

        if sentiment > 0.3:
            action = "buy"
            confidence = round(min(1.0, sentiment), 2)
        elif sentiment < -0.3:
            action = "sell"
            confidence = round(min(1.0, abs(sentiment)), 2)
        else:
            action = "hold"
            confidence = 0.5

        return Decision(
            action=action,
            params={
                "market_ids": market_ids,
                "context": context,
            },
            confidence=confidence,
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
            suggested_improvement: str | None = None
        else:
            insight = f"Action failed: {outcome.error or 'unknown error'}"
            suggested_improvement = "Review the error and adjust the decision parameters"

        return Reflection(
            insight=insight,
            suggested_improvement=suggested_improvement,
        )
