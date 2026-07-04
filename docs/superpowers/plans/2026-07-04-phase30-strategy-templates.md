# Phase 30: Strategy Templates Library — Implementation Plan

**Date:** 2026-07-04

---

### Task 1: Create base template types

**File:** `polymind/templates/base.py`

```
TemplateInfo: name, description, strategy_type, params, risk_limits, tags
```

### Task 2: Create template library

**File:** `polymind/templates/library.py`

TemplateLibrary with all built-in templates, list/get/instantiate methods.

### Task 3: Create individual templates

Files: `polymind/templates/amm_concentrated.py` etc.

### Task 4: CLI integration

Add `templates` and `template run/show` commands to CLI.

### Task 5: Tests

**File:** `tests/templates/test_library.py`
**File:** `tests/templates/test_amm_template.py`

### Task 6: Full test suite
