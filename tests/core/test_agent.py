"""
Tests for BaseAgent and AgentMemory.
"""

from __future__ import annotations

from datetime import datetime

import pytest

from polymind.core.agent import AgentMemory, BaseAgent, Decision, Observation


class SimpleMock:
    """Lightweight mock for position objects returned by get_positions()."""

    def __init__(self, **kwargs):
        for k, v in kwargs.items():
            setattr(self, k, v)


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
        decision = Decision(action="buy", market_id="0xabc", outcome="YES", size=10.0, price=0.5)
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
        decision = Decision(action="buy", market_id="0xabc", outcome="YES", size=10.0)
        result = await agent.act(decision)
        assert result is True

    @pytest.mark.asyncio
    async def test_act_real_execution_non_hold(self):
        """act() with non-hold, non-dry run with mock client."""
        agent = self._TestAgent()
        agent.dry_run = False
        decision = Decision(action="close", market_id="0xabc", outcome="YES")
        result = await agent.act(decision)
        assert result is True

    # --- REF-001b: Position dedup ---

    @pytest.mark.asyncio
    async def test_has_position_returns_false_initially(self):
        agent = self._TestAgent()
        assert agent._has_position("0x1", "YES") is False

    @pytest.mark.asyncio
    async def test_record_position_then_has_position(self):
        agent = self._TestAgent()
        agent._record_position("0x1", "YES")
        assert agent._has_position("0x1", "YES") is True
        assert agent._has_position("0x1", "NO") is False

    @pytest.mark.asyncio
    async def test_discard_position_removes_it(self):
        agent = self._TestAgent()
        agent._record_position("0x1", "YES")
        assert agent._has_position("0x1", "YES") is True
        agent._discard_position("0x1", "YES")
        assert agent._has_position("0x1", "YES") is False

    @pytest.mark.asyncio
    async def test_discard_nonexistent_position_does_not_raise(self):
        agent = self._TestAgent()
        agent._discard_position("0xmissing", "YES")  # should not raise
        assert len(agent._open_positions) == 0

    @pytest.mark.asyncio
    async def test_buy_skip_existing_position(self):
        """act('buy') skips when position already tracked (dedup)."""
        agent = self._TestAgent()
        agent._record_position("0x1", "YES")  # already have it
        result = await agent.act(Decision(action="buy", market_id="0x1", outcome="YES"))
        assert result is True  # not an error, just skip
        # Still only one entry (did not double-add)
        assert len([k for k in agent._open_positions if k == "0x1:YES"]) == 1

    @pytest.mark.asyncio
    async def test_buy_records_position_when_new(self):
        """act('buy') records position when no existing position."""
        agent = self._TestAgent()
        result = await agent.act(Decision(action="buy", market_id="0x1", outcome="YES"))
        assert result is True
        assert agent._has_position("0x1", "YES") is True

    @pytest.mark.asyncio
    async def test_buy_missing_fields_returns_false(self):
        agent = self._TestAgent()
        result = await agent.act(Decision(action="buy"))  # no market_id / outcome
        assert result is False

    @pytest.mark.asyncio
    async def test_act_sell_discards_position(self):
        agent = self._TestAgent()
        agent._record_position("0x1", "YES")
        result = await agent.act(Decision(action="sell", market_id="0x1", outcome="YES"))
        assert result is True
        assert agent._has_position("0x1", "YES") is False

    @pytest.mark.asyncio
    async def test_act_close_discards_position(self):
        agent = self._TestAgent()
        agent._record_position("0x1", "YES")
        result = await agent.act(Decision(action="close", market_id="0x1", outcome="YES"))
        assert result is True
        assert agent._has_position("0x1", "YES") is False

    @pytest.mark.asyncio
    async def test_observe_syncs_api_positions(self):
        """observe() syncs positions from API response into _open_positions."""
        from unittest.mock import AsyncMock

        agent = self._TestAgent()
        mock = AsyncMock()
        mock.get_markets = AsyncMock(return_value=[])
        mock.get_positions = AsyncMock(
            return_value=[
                SimpleMock(market_id="0xa", outcome="YES", size=10),
                SimpleMock(market_id="0xa", outcome="NO", size=5),
            ]
        )
        mock.get_balance = AsyncMock(return_value=100.0)
        agent.client = mock
        await agent.observe()
        assert agent._has_position("0xa", "YES") is True
        assert agent._has_position("0xa", "NO") is True
        assert agent._has_position("0xb", "YES") is False

    @pytest.mark.asyncio
    async def test_observe_empty_positions(self):
        """observe() with no positions leaves set empty."""
        from unittest.mock import AsyncMock

        agent = self._TestAgent()
        mock = AsyncMock()
        mock.get_markets = AsyncMock(return_value=[])
        mock.get_positions = AsyncMock(return_value=[])
        mock.get_balance = AsyncMock(return_value=100.0)
        agent.client = mock
        await agent.observe()
        assert len(agent._open_positions) == 0

    @pytest.mark.asyncio
    async def test_buy_dry_run_records_position(self):
        agent = self._TestAgent()
        agent.dry_run = True
        result = await agent.act(Decision(action="buy", market_id="0x1", outcome="YES"))
        assert result is True
        assert agent._has_position("0x1", "YES") is True

    @pytest.mark.asyncio
    async def test_run_loop_skip_duplicate_buy(self):
        """Full loop: buy a position twice -> second act skips."""
        import asyncio

        agent = self._TestAgent()
        agent.loop_interval = 0.005
        call_count = 0

        async def alternating_decide(obs):
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                return Decision(action="buy", market_id="0x1", outcome="YES", reasoning="first")
            return Decision(action="buy", market_id="0x1", outcome="YES", reasoning="dup")

        agent.decide = alternating_decide  # type: ignore[assignment]

        loop_task = asyncio.create_task(agent.run_loop())
        await asyncio.sleep(0.03)
        agent.stop()
        await loop_task

        # Position recorded once despite two buy decisions
        assert len(agent._open_positions) == 1
        assert agent._has_position("0x1", "YES") is True

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


class TestAgentMemory:
    """Tests for AgentMemory bounded-memory collection."""

    @pytest.mark.asyncio
    async def test_add_observation(self):
        mem = AgentMemory()
        now = datetime.now()
        obs = Observation(timestamp=now, markets=["m1"])
        await mem.add_observation(obs)
        assert len(mem.observations) == 1
        assert mem.observations[0].markets == ["m1"]

    @pytest.mark.asyncio
    async def test_add_decision(self):
        mem = AgentMemory()
        dec = Decision(action="buy", market_id="0x1", size=10.0)
        await mem.add_decision(dec)
        assert len(mem.decisions) == 1
        assert mem.decisions[0].action == "buy"

    @pytest.mark.asyncio
    async def test_bounded_length(self):
        """Deque maxlen=100 evicts oldest entries."""
        mem = AgentMemory()
        for i in range(110):
            await mem.add_decision(Decision(action="hold", reasoning=f"step-{i}"))
        assert len(mem.decisions) == 100
        # Oldest evicted: first entry should be step-10 (not step-0)
        assert mem.decisions[0].reasoning == "step-10"

    @pytest.mark.asyncio
    async def test_thread_safe_concurrent_add(self):
        """Concurrent adds do not lose entries."""
        import asyncio

        mem = AgentMemory()

        async def add_obs(i: int):
            await mem.add_observation(
                Observation(
                    timestamp=datetime.now(),
                    markets=[f"m{i}"],
                )
            )

        await asyncio.gather(*[add_obs(i) for i in range(50)])
        assert len(mem.observations) == 50
        market_ids = {o.markets[0] for o in mem.observations}
        assert len(market_ids) == 50

    def test_get_recent_history_empty(self):
        mem = AgentMemory()
        history = mem.get_recent_history(n=5)
        assert history == ""

    @pytest.mark.asyncio
    async def test_get_recent_history(self):
        mem = AgentMemory()
        now = datetime(2026, 7, 6, 12, 0, 0)
        await mem.add_observation(
            Observation(timestamp=now, markets=["m1"], positions=[], balance=100.0)
        )
        await mem.add_decision(Decision(action="buy", market_id="0x1", reasoning="signal strong"))
        history = mem.get_recent_history(n=5)
        assert "12:00:00" in history
        assert "Markets: 1" in history
        assert "Balance: 100.0" in history
        assert "signal strong" in history

    @pytest.mark.asyncio
    async def test_base_agent_has_memory(self):
        """BaseAgent initialises with an AgentMemory."""
        agent = TestBaseAgent._TestAgent()
        assert hasattr(agent, "memory")
        assert isinstance(agent.memory, AgentMemory)

    @pytest.mark.asyncio
    async def test_observe_records_to_memory(self):
        """BaseAgent.observe() records the observation to memory."""
        agent = TestBaseAgent._TestAgent()
        obs = await agent.observe()
        assert len(agent.memory.observations) == 1
        assert agent.memory.observations[0] is obs

    @pytest.mark.asyncio
    async def test_act_records_to_memory(self):
        """BaseAgent.act() records the decision to memory."""
        agent = TestBaseAgent._TestAgent()
        dec = Decision(action="hold")
        await agent.act(dec)
        assert len(agent.memory.decisions) == 1
        assert agent.memory.decisions[0] is dec

    @pytest.mark.asyncio
    async def test_run_loop_records_observation_and_decision(self):
        """Full observe→decide→act loop writes to memory."""
        import asyncio

        agent = TestBaseAgent._TestAgent()
        agent.loop_interval = 0.01

        async def stop_after():
            await asyncio.sleep(0.03)
            agent.stop()

        loop_task = asyncio.create_task(agent.run_loop())
        await asyncio.sleep(0.05)
        agent.stop()
        await loop_task
        assert len(agent.memory.observations) >= 1
        assert len(agent.memory.decisions) >= 1
