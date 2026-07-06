# Validation Gates (GAP-011)

Every generated strategy config passes through a three-gate validation
pipeline before it is marked `validated=True`.  Gates run in sequence;
all must pass.

## Gate 1: Schema

**File:** `generator._validate_schema()`

Checks that the generated params satisfy the template's contract:

- **Required params** — every param listed in
  `StrategyTemplate.required_params` must be present in `config.params`.
- **Type correctness** — each known param is checked against a type
  table (`_PARAM_TYPES`).  For example `num_levels` must be `int`,
  `min_spread` must be numeric (`int` or `float`).  Unknown params are
  allowed (no type check).

**Fails when:** a required param is missing or a type is wrong.

## Gate 2: Implementation Status

**File:** `generator._validate_implementation_status()`

Verifies that the generated strategy template has a matching plugin
registered in `PluginRegistry`.

- Looks up `config.template.value` (e.g. `"amm"`, `"bands"`) via
  `PluginRegistry().get_strategy()`.
- **Meta-templates** (`CUSTOM`, `FACTOR`) are exempt — they are
  handled by dynamic routing and do not require a direct plugin
  registration.

**Fails when:** the template name is not in the registry's strategy
map and is not a meta-template.

## Gate 3: Risk Limits

**File:** `generator._validate_risk_limits()`

Checks that strategy parameters do not exceed configured risk limits.
The limits are defined in the `_RISK_LIMITS` dict at module level.

| Parameter          | Limit         | Notes                     |
|--------------------|---------------|---------------------------|
| `num_levels`       | max 20        | Prevents excessive ladder |
| `top_n`            | max 50        | Prevents over-diversified hold |
| `total_exposure`   | max 100 000   | USD-equivalent cap        |
| `exposure_per_band`| max 50 000   | Per-band risk cap         |
| `min_spread`       | min 0.0001   | 0.01 % floor              |
| `max_spread`       | max 0.50     | 50 % ceiling              |

Only params that are **present** in the config are checked — absent
params are skipped (the gate does not inject defaults).

**Fails when:** any present param exceeds its limit.

## Execution Order

```
validate()
  ├── _validate_schema(config)         ← Gate 1
  ├── _validate_implementation_status(config)  ← Gate 2
  └── _validate_risk_limits(config)    ← Gate 3
```

`_validate()` iterates gates in order, collects all results, then sets
`config.validated = all(g.passed for g in gates)` and stores the
individual `ValidationGate` objects in `config.validation_results`.

## What Happens on Failure

- `config.validated` is set to `False`.
- The strategy **is still generated** and returned — the gates are
  advisory/audit, not blocking.
- `config.validation_results` contains the full result of every gate,
  so callers can inspect which gate(s) failed and why.
- Downstream consumers (e.g. the studio UI, deployment pipeline) can
  check `validated` and decide whether to show a warning or enforce a
  hard block.

## Adding a New Gate

1. Add a method `_validate_<name>(self, config) -> ValidationGate` to
   `StrategyGenerator`.
2. Add the method call to the gates list in `_validate()`.
3. Add the gate name to test `test_validation_results_populated` in
   `tests/studio/test_generator.py`.
4. If the gate needs new risk-limit constants, add them to
   `_RISK_LIMITS` and document in the table above.

Keep gates independent — each one inspects `config` and returns a
`ValidationGate` without modifying the config or depending on the
result of another gate.
