"""Ensemble agent — wraps multiple agents with orchestration strategies."""

from __future__ import annotations

from enum import Enum, auto

from polymind.agents.base import (
    ActionResult,
    AgentConfig,
    BaseAgent,
    Decision,
    Observation,
    Reflection,
)


class EnsembleStrategy(Enum):
    """Strategies for aggregating sub-agent decisions."""

    FIRST_RESPONDER = auto()  # Return the first agent's decision
    WEIGHTED_VOTE = auto()  # Pick decision with highest confidence
    MAJORITY = auto()  # Majority vote on action strings


class EnsembleAgent(BaseAgent):
    """Agent that wraps multiple sub-agents and coordinates their decisions.

    Supports three ensemble strategies:
    - FIRST_RESPONDER: Returns the first agent's decision.
    - WEIGHTED_VOTE: Picks the decision with the highest confidence.
    - MAJORITY: Picks the action with the most votes.
    """

    def __init__(
        self,
        config: AgentConfig,
        agents: list[BaseAgent],
        strategy: EnsembleStrategy = EnsembleStrategy.FIRST_RESPONDER,
    ) -> None:
        super().__init__(config)
        if not agents:
            raise ValueError("EnsembleAgent requires at least one sub-agent")
        self._agents = agents
        self._strategy = strategy

    @property
    def agents(self) -> list[BaseAgent]:
        """Return the list of sub-agents."""
        return self._agents

    @property
    def strategy(self) -> EnsembleStrategy:
        """Return the ensemble strategy."""
        return self._strategy

    async def decide(self, observation: Observation) -> Decision:
        """Run all sub-agents and aggregate per strategy."""
        from asyncio import gather

        raw = await gather(*[a.decide(observation) for a in self._agents])

        if self._strategy == EnsembleStrategy.FIRST_RESPONDER:
            decision = raw[0]
            decision.params = {**decision.params, "_ensemble_agent_index": 0}
            return decision

        if self._strategy == EnsembleStrategy.WEIGHTED_VOTE:
            best = max(raw, key=lambda d: d.confidence)
            idx = raw.index(best)
            best.params = {**best.params, "_ensemble_agent_index": idx}
            return best

        # MAJORITY
        vote_counts: dict[str, int] = {}
        for d in raw:
            vote_counts[d.action] = vote_counts.get(d.action, 0) + 1
        best_action: str = max(vote_counts, key=vote_counts.__getitem__)  # type: ignore[type-var]
        for i, d in enumerate(raw):
            if d.action == best_action:
                d.params = {**d.params, "_ensemble_agent_index": i}
                return d

        fallback = raw[0]
        fallback.params = {**fallback.params, "_ensemble_agent_index": 0}
        return fallback

    async def act(self, decision: Decision) -> ActionResult:
        """Delegate to the agent that produced the decision.

        Uses the ``_ensemble_agent_index`` param (set by ``decide()``) to
        route execution to the correct sub-agent.
        """
        agent_index = decision.params.get("_ensemble_agent_index")
        if agent_index is not None and 0 <= agent_index < len(self._agents):
            return await self._agents[agent_index].act(decision)
        return await self._agents[0].act(decision)

    async def reflect(self, outcome: ActionResult) -> Reflection:
        """Collect reflections from all sub-agents.

        Returns the reflection from the first sub-agent.
        """
        from asyncio import gather

        reflections = await gather(*[a.reflect(outcome) for a in self._agents])
        return reflections[0]
