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
#: Per-request wall-clock cap. Without one the SDK waits on its own
#: default, and a stalled connection can hang a whole benchmark run --
#: config.yaml has carried `llm.timeout_seconds: 60` since the start, but
#: nothing read it, so no timeout was ever applied.
DEFAULT_TIMEOUT_SECONDS = 60.0


class LLMConfigError(RuntimeError):
    """Raised when the LLM client can't be configured (e.g. no API key)."""


class LLMResponseError(RuntimeError):
    """Raised when the LLM returns an unusable response (refusal/truncation)."""


class LLMClient:
    """Wrapper around ``anthropic.Anthropic`` for JSON-constrained calls."""

    def __init__(self, model: str = DEFAULT_MODEL, api_key: str | None = None,
                 max_retries: int = 3,
                 timeout: float | None = DEFAULT_TIMEOUT_SECONDS):
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
        self.timeout = timeout
        self.client = anthropic.Anthropic(api_key=key, max_retries=max_retries,
                                          timeout=timeout)

    # ------------------------------------------------------------------ API
    def extract_json(
        self,
        prompt: str,
        schema: dict[str, Any],
        system: str | None = None,
        max_tokens: int = DEFAULT_MAX_TOKENS,
        image_path: str | None = None,
    ) -> dict[str, Any]:
        """Call Claude and return a dict guaranteed to match ``schema``.

        Uses ``output_config.format`` so the model's response is constrained
        to the JSON Schema — the returned text is valid JSON matching it.
        When ``image_path`` is given the image is attached to the message
        (Claude is multimodal), enabling checks against what the figure
        actually shows rather than heuristic pixel counting.
        Raises :class:`LLMResponseError` on refusal or truncation.
        """
        if image_path:
            content: Any = [
                {"type": "image",
                 "source": {"type": "base64", "media_type": "image/jpeg",
                            "data": _encode_image_jpeg_b64(image_path)}},
                {"type": "text", "text": prompt},
            ]
        else:
            content = prompt
        try:
            response = self.client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                system=system or "You output only valid JSON matching the schema.",
                messages=[{"role": "user", "content": content}],
                output_config={"format": {"type": "json_schema", "schema": schema}},
            )
        except self._anthropic.AuthenticationError as exc:
            raise LLMConfigError("Claude API rejected the API key (401). Check "
                                 "ANTHROPIC_API_KEY.") from exc
        except self._anthropic.APIStatusError as exc:  # 4xx/5xx after retries
            raise LLMResponseError(f"Claude API error {exc.status_code}: "
                                   f"{exc.message}") from exc
        except self._anthropic.APITimeoutError as exc:
            raise LLMResponseError(
                f"the Claude API did not respond within {self.timeout}s "
                f"(llm.timeout_seconds). Raise it, or check the network."
            ) from exc
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


def _encode_image_jpeg_b64(image_path: str, max_side: int = 1536,
                           quality: int = 85) -> str:
    """Load an image, bound its size, and return base64-encoded JPEG bytes.

    Downscaling to ``max_side`` keeps requests small and within the API's
    image limits without hurting panel/lane counting.
    """
    import base64
    import io

    from PIL import Image

    with Image.open(image_path) as img:
        img = img.convert("RGB")
        longest = max(img.size)
        if longest > max_side:
            scale = max_side / longest
            img = img.resize((max(1, int(img.width * scale)),
                              max(1, int(img.height * scale))))
        buf = io.BytesIO()
        img.save(buf, format="JPEG", quality=quality)
    return base64.b64encode(buf.getvalue()).decode("ascii")


# Load a .env file if python-dotenv is available, so ANTHROPIC_API_KEY can
# live in a local .env rather than the shell environment. Best-effort.
def _load_dotenv() -> None:
    try:
        from dotenv import load_dotenv
        load_dotenv()
    except ImportError:  # pragma: no cover - optional dependency
        pass


_load_dotenv()
