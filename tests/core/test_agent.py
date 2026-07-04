"""
Tests for BaseAgent.
"""

from __future__ import annotations

from datetime import datetime

import pytest

from polymind.core.agent import BaseAgent, Decision, Observation


class TestObservation:
    def test_minimal(self):
        now = datetime.now()
        obs = Observation(timestamp=now, markets=[], positions=[])
        assert obs.timestamp == now
        assert obs.markets == []
        assert obs.positions == []


class TestBaseAgent:
    class _TestAgent(BaseAgent):
        """Concrete agent for testing."""

        def __init__(self):
            super().__init__(name="test_agent", loop_interval=1)

        async def decide(self, observation: Observation) -> Decision:
            return Decision(action="hold", reasoning="no action needed")

    @pytest.mark.asyncio
    async def test_agent_name(self):
        agent = self._TestAgent()
        assert agent.name == "test_agent"

    @pytest.mark.asyncio
    async def test_decide(self):
        agent = self._TestAgent()
        now = datetime.now()
        obs = Observation(timestamp=now, markets=["m1", "m2"])
        decision = await agent.decide(obs)
        assert decision.action == "hold"
        assert decision.reasoning == "no action needed"

    @pytest.mark.asyncio
    async def test_act_hold(self):
        agent = self._TestAgent()
        decision = Decision(action="hold")
        result = await agent.act(decision)
        assert result is True

    @pytest.mark.asyncio
    async def test_dry_run(self):
        agent = self._TestAgent()
        agent.dry_run = True
        decision = Decision(action="buy", market_id="0xabc", size=10.0, price=0.5)
        result = await agent.act(decision)
        assert result is True

    @pytest.mark.asyncio
    async def test_stop(self):
        agent = self._TestAgent()
        assert agent._running is False
        agent.stop()

    @pytest.mark.asyncio
    async def test_loop_interval(self):
        agent = self._TestAgent()
        assert agent.loop_interval == 1
        assert agent.dry_run is False

    @pytest.mark.asyncio
    async def test_observe_no_client(self):
        """observe() with no client returns empty observation (lines 62-64)."""
        agent = self._TestAgent()
        agent.client = None
        obs = await agent.observe()
        assert isinstance(obs, Observation)
        assert obs.markets == []
        assert obs.positions == []
        assert obs.balance == 0.0

    @pytest.mark.asyncio
    async def test_decide_abstract_body(self):
        """Line 58: class-dispatch to BaseAgent.decide hits the abstract ellipsis body."""
        agent = self._TestAgent()
        obs = Observation(timestamp=datetime.now())
        result = await BaseAgent.decide(agent, obs)
        assert result is None  # ellipsis body returns None

    @pytest.mark.asyncio
    async def test_act_non_hold_not_dry(self):
        """act() with non-hold action, not dry run (line 87)."""
        agent = self._TestAgent()
        agent.dry_run = False
        decision = Decision(action="buy", market_id="0xabc", size=10.0)
        result = await agent.act(decision)
        assert result is True

    @pytest.mark.asyncio
    async def test_act_real_execution_non_hold(self):
        """act() with non-hold, non-dry run with mock client."""
        agent = self._TestAgent()
        agent.dry_run = False
        decision = Decision(action="close", market_id="0xabc")
        result = await agent.act(decision)
        assert result is True

    @pytest.mark.asyncio
    async def test_observe_with_mock_client(self):
        """observe() with mock client calls client methods (lines 66-71)."""
        from unittest.mock import AsyncMock

        agent = self._TestAgent()
        mock = AsyncMock()
        mock.get_markets = AsyncMock(return_value=["m1"])
        mock.get_positions = AsyncMock(return_value=["p1"])
        mock.get_balance = AsyncMock(return_value=1000.0)
        agent.client = mock
        obs = await agent.observe()
        assert obs.markets == ["m1"]
        assert obs.positions == ["p1"]
        assert obs.balance == 1000.0
        mock.get_markets.assert_awaited_once()
        mock.get_positions.assert_awaited_once()
        mock.get_balance.assert_awaited_once()

    @pytest.mark.asyncio
    async def test_run_loop_stop(self):
        """run_loop() can be stopped (lines 91-101)."""
        import asyncio

        agent = self._TestAgent()
        agent.loop_interval = 0.01

        async def stop_after():
            await asyncio.sleep(0.02)
            agent.stop()

        loop_task = asyncio.create_task(agent.run_loop())
        await asyncio.sleep(0.03)
        agent.stop()
        await loop_task
        assert agent._running is False

    @pytest.mark.asyncio
    async def test_run_loop_cancelled(self):
        """run_loop() handles CancelledError gracefully (line 98-99)."""
        import asyncio

        agent = self._TestAgent()
        agent.loop_interval = 0.5  # long interval so it stays in sleep

        task = asyncio.create_task(agent.run_loop())
        await asyncio.sleep(0.05)
        task.cancel()
        await asyncio.sleep(0.05)
        assert agent._running is False
