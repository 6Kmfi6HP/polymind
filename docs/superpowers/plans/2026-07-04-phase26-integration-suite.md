# Phase 26: Integration Test Suite — Implementation Plan

**Date:** 2026-07-04

---

### Task 1: Full Pipeline — Strategy → TradingEngine → Executor

**File:** `tests/integration/test_full_pipeline.py`

```
TestFullPipeline:
  test_full_pipeline_amm_strategy:
    - register_builtin_strategies()   (called at import time)
    - Create FillModel(mode=FillMode.TAKER)
    - Create PaperExecutor(fill_model)
    - Get AMMStrategy via get_strategy("amm")
    - Create TradingEngine(strategy, executor)
    - Build MarketSnapshot(market_id, bid_price, ask_price, mid_price, ...)
    - result = await engine.run_tick(market)
    - assert result.orders_proposed > 0
    - assert result.orders_placed > 0
    - assert result.risk_approved == True
    - assert result.error == ""
    - assert len(executor.orders) > 0
    - assert executor.cash < executor.initial_cash  (if fills occurred)
```

### Task 2: Workflow Integration — WorkflowRunner → PairLifecycleManager

**File:** `tests/integration/test_workflow_integration.py`

```
TestWorkflowIntegration:
  test_start_maker_rebate_workflow:
    - Create PairLifecycleManager(mock_gateway)
    - Create WorkflowRunner(pair_lifecycle=manager)
    - cmd = WorkflowCommand("rebate-001", CommandType.START, {"type": "maker_rebate"})
    - result = await runner.process_command(cmd)
    - assert result.success == True
    - assert result.state == "PLACING_ORDERS"
    - instances = runner.list_instances()
    - assert "rebate-001" in instances

  test_halt_maker_rebate_workflow:
    - Start workflow, then send STOP
    - Verify state transitions to HALTED

  test_pair_lifecycle_split_via_runner:
    - Register market on PairLifecycleManager
    - Mock gateway.split on the gateway
    - cmd = WorkflowCommand("rebate-001", CommandType.SPLIT, params={...})
    - result = await runner.process_command(cmd)
    - assert result.success == True
```

### Task 3: Risk Integration — TradingEngine + RiskGate

**File:** `tests/integration/test_risk_integration.py`

```
class MaxPositionGate(RiskGate):
  """Rejects intents where any order.size > max_size."""
  name = "MaxPositionGate"
  async def evaluate(self, intent, context) -> RiskDecision:
    for order in intent.orders:
      if order.size > self.max_size:
        return RiskDecision(gate_name=self.name, approved=False, reason=...)
    return RiskDecision(gate_name=self.name, approved=True, reason="ok")

TestRiskIntegration:
  test_risk_rejects_oversized_intent:
    - Gate with max_size=5.0
    - Strategy produces order with size=100.0
    - engine.run_tick(market)
    - assert result.risk_approved == False
    - assert "max_size" in result.error.lower()

  test_risk_passes_compliant_intent:
    - Same gate, but strategy produces order with size=5.0
    - assert result.risk_approved == True
```

### Task 4: Multi-Strategy Swap

**File:** `tests/integration/test_multi_strategy.py`

```
TestMultiStrategy:
  test_each_builtin_strategy_produces_intents:
    strategies_to_test = ["amm", "bands", "classic_mm", "maker_rebate"]
    for name in strategies_to_test:
      strategy = get_strategy(name)
      engine = TradingEngine(strategy, executor)
      result = await engine.run_tick(market)
      assert result.orders_proposed > 0, f"{name} produced no orders"
      assert result.strategy == strategy.name
      assert result.risk_approved == True
```
