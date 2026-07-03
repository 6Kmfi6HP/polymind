# Phase 12: Agent Provider Implementation — Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development

**Goal:** Implement Anthropic, OpenAI, Gemini, Ensemble, and Intelligence agent providers.

**Architecture:** Each provider extends `BaseAgent` from `polymind/agents/base.py`. They follow the existing contract and use optional dependencies.

**Tech Stack:** Python 3.10+, anthropic, openai, google-genai SDKs (optional)

## Global Constraints

- All providers use lazy imports for their SDKs (keep as optional dependencies)
- Must follow `BaseAgent` ABC contract exactly
- All new modules must have tests
- No changes to existing `base.py`

---

### Task 1: AnthropicAgent

**Files:**
- Create: `polymind/agents/anthropic.py`
- Test: `tests/agents/test_anthropic.py`

### Task 2: OpenAIAgent

**Files:**
- Create: `polymind/agents/openai.py`
- Test: `tests/agents/test_openai.py`

### Task 3: GeminiAgent

**Files:**
- Create: `polymind/agents/gemini.py`
- Test: `tests/agents/test_gemini.py`

### Task 4: EnsembleAgent & IntelligenceAgent

**Files:**
- Create: `polymind/agents/ensemble.py`, `polymind/agents/intelligence.py`
- Test: `tests/agents/test_ensemble.py`, `tests/agents/test_intelligence.py`

### Task 5: Agent Package Exports & Verification

- Update `polymind/agents/__init__.py`
- Run full test suite
