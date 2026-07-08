"""Anthropic Claude API wrapper for ScholarGuard.

Thin, dependency-light client used by the NLP stage. Responsibilities:

* Read the API key from ``ANTHROPIC_API_KEY`` (never hardcoded); raise a
  clear, actionable error if it is missing.
* Enforce **structured JSON output** via ``output_config.format`` — the model
  is constrained to a JSON Schema, so the response is guaranteed to parse and
  match the expected shape (no fragile "please output JSON" prompting).
* Retry transient failures (the SDK already retries 429/5xx; we add a small
  extra guard and surface non-retryable errors with a helpful message).

Default model is ``claude-opus-4-8``. Callers can override per request.
"""

from __future__ import annotations

import json
import os
from typing import Any

DEFAULT_MODEL = "claude-opus-4-8"
DEFAULT_MAX_TOKENS = 2048


class LLMConfigError(RuntimeError):
    """Raised when the LLM client can't be configured (e.g. no API key)."""


class LLMClient:
    """Wrapper around ``anthropic.Anthropic`` for JSON-constrained calls."""

    def __init__(self, model: str = DEFAULT_MODEL, api_key: str | None = None,
                 max_retries: int = 3):
        # anthropic is imported lazily so the rest of ScholarGuard (and the
        # unit tests, which mock this client) works without the SDK/key.
        try:
            import anthropic
        except ImportError as exc:  # pragma: no cover - environment issue
            raise LLMConfigError(
                "the 'anthropic' package is required for the NLP stage. "
                "Install it with: pip install anthropic"
            ) from exc

        key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not key:
            raise LLMConfigError(
                "ANTHROPIC_API_KEY is not set. Export your Claude API key, e.g.\n"
                "  export ANTHROPIC_API_KEY=sk-ant-...      (bash)\n"
                "  $env:ANTHROPIC_API_KEY = 'sk-ant-...'    (PowerShell)\n"
                "or place it in a .env file (python-dotenv is loaded automatically)."
            )
        self._anthropic = anthropic
        self.model = model
        self.client = anthropic.Anthropic(api_key=key, max_retries=max_retries)

    # ------------------------------------------------------------------ API
    def extract_json(
        self,
        prompt: str,
        schema: dict[str, Any],
        system: str | None = None,
        max_tokens: int = DEFAULT_MAX_TOKENS,
    ) -> dict[str, Any]:
        """Call Claude and return a dict guaranteed to match ``schema``.

        Uses ``output_config.format`` so the model's response is constrained
        to the JSON Schema — the returned text is valid JSON matching it.
        Raises :class:`LLMResponseError` on refusal or truncation.
        """
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                system=system or "You output only valid JSON matching the schema.",
                messages=[{"role": "user", "content": prompt}],
                output_config={"format": {"type": "json_schema", "schema": schema}},
            )
        except self._anthropic.AuthenticationError as exc:
            raise LLMConfigError("Claude API rejected the API key (401). Check "
                                 "ANTHROPIC_API_KEY.") from exc
        except self._anthropic.APIStatusError as exc:  # 4xx/5xx after retries
            raise LLMResponseError(f"Claude API error {exc.status_code}: "
                                   f"{exc.message}") from exc
        except self._anthropic.APIConnectionError as exc:
            raise LLMResponseError("could not reach the Claude API (network "
                                   "error).") from exc

        if response.stop_reason == "refusal":
            raise LLMResponseError("the model declined to answer this request.")
        if response.stop_reason == "max_tokens":
            raise LLMResponseError("response was truncated (max_tokens); raise "
                                   "max_tokens and retry.")

        # output_config.format guarantees the first text block is valid JSON.
        text = next((b.text for b in response.content if b.type == "text"), "")
        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:  # pragma: no cover - shouldn't happen
            raise LLMResponseError(f"model returned non-JSON output: {text[:200]}") \
                from exc


class LLMResponseError(RuntimeError):
    """Raised when the LLM returns an unusable response (refusal/truncation)."""


# Load a .env file if python-dotenv is available, so ANTHROPIC_API_KEY can
# live in a local .env rather than the shell environment. Best-effort.
def _load_dotenv() -> None:
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:  # pragma: no cover - optional dependency
        pass


_load_dotenv()
