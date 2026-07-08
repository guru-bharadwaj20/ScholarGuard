"""LLM integration for ScholarGuard's NLP stage.

Thin wrapper around the Anthropic Claude API (:mod:`src.llm.client`) plus
the prompt templates (:mod:`src.llm.prompts`). The API key is read from the
``ANTHROPIC_API_KEY`` environment variable — never hardcoded.
"""
