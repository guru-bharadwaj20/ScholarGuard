"""Extract structured, checkable claims about a figure from paper text.

Wraps :class:`src.llm.client.LLMClient` with the claim-extraction prompt and
JSON Schema from :mod:`src.llm.prompts`. Because the call uses structured
outputs (``output_config.format``), the returned dict is guaranteed to match
the schema — callers can rely on the keys always being present.
"""

from __future__ import annotations

from src.llm.client import LLMClient
from src.llm.prompts import (
    CLAIM_EXTRACTION_SCHEMA,
    CLAIM_EXTRACTION_SYSTEM,
    build_claim_extraction_prompt,
)

# The shape returned when no text is available or the LLM can't be reached, so
# downstream consistency checking always has a well-formed dict to work with.
EMPTY_CLAIMS: dict = {
    "claimed_description": None,
    "claimed_n": None,
    "claimed_panel_count": None,
    "panel_count_kind": None,
    "claimed_stats": [],
    "error_bar_description": None,
}


def extract_claims(
    figure_caption: str,
    results_text: str,
    figure_label: str = "the figure",
    client: LLMClient | None = None,
) -> dict:
    """Extract structured claims about one figure from its caption + context.

    Returns a dict matching ``CLAIM_EXTRACTION_SCHEMA``:
    ``{"claimed_description", "claimed_n", "claimed_panel_count",
    "panel_count_kind", "claimed_stats": [...], "error_bar_description"}``.

    ``client`` is injectable so tests can supply a mock and CI never spends
    API credits. With no caption or context, returns ``EMPTY_CLAIMS`` without
    calling the API.
    """
    if not (figure_caption.strip() or results_text.strip()):
        return dict(EMPTY_CLAIMS)

    client = client or LLMClient()
    prompt = build_claim_extraction_prompt(figure_label, figure_caption,
                                           results_text)
    claims = client.extract_json(
        prompt,
        schema=CLAIM_EXTRACTION_SCHEMA,
        system=CLAIM_EXTRACTION_SYSTEM,
    )
    # Defensive: guarantee all keys exist even if a future schema drifts.
    return {**EMPTY_CLAIMS, **claims}
