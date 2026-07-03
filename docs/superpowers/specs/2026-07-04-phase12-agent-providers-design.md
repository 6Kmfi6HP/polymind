# Phase 12: Agent Provider Implementation — Design

**Status:** Approved Design
**Date:** 2026-07-04

## Overview

Implement the AI provider agent classes referenced in the architecture but not yet implemented. These provide LLM integration for natural-language strategy generation and execution.

## Architecture

```
polymind/agents/
├── base.py         # BaseAgent ABC (existing)
├── anthropic.py    # Anthropic Claude provider (new)
├── openai.py       # OpenAI GPT provider (new)
├── gemini.py       # Google Gemini provider (new)
├── ensemble.py     # Multi-provider ensemble (new)
└── intelligence.py # News/sentiment context (new)
```

## Components

### AnthropicAgent
- Uses `anthropic` SDK via optional dependency
- `generate()`: text generation with tool use
- Configurable model, temperature, max_tokens

### OpenAIAgent
- Uses `openai` SDK via optional dependency
- `generate()`: chat completions
- Configurable model, temperature, max_tokens

### GeminiAgent
- Uses `google-genai` SDK via optional dependency
- `generate()`: text generation
- Configurable model, temperature

### EnsembleAgent
- Wraps multiple agents, returns consensus/vote
- Strategies: first-responder, weighted-vote, majority

### IntelligenceAgent
- Market/news context enrichment for strategy prompts
- Fetches relevant context from external sources

## Dependencies

All providers use optional dependencies (already defined in pyproject.toml):
- `polymind[anthropic]`
- `polymind[openai]`
- `polymind[google]`
