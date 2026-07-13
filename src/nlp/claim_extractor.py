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
    FIGURE_VISION_SCHEMA,
    FIGURE_VISION_SYSTEM,
    build_claim_extraction_prompt,
    build_figure_vision_prompt,
)

# The shape returned when the vision model can't be reached, so consistency
# checking always has a well-formed observation dict.
EMPTY_OBSERVATIONS: dict = {
    "observed_panel_count": None,
    "panel_letters": [],
    "observed_lane_count": None,
    "techniques": [],
    "visible_text_labels": [],
    "notable_observations": None,
}

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


def observe_figure(
    image_path: str,
    figure_caption: str = "",
    figure_label: str = "the figure",
    client: LLMClient | None = None,
) -> dict:
    """Observe what a figure image actually shows, via the vision model.

    Returns a dict matching ``FIGURE_VISION_SCHEMA`` (panel/lane counts,
    techniques, visible labels, notable observations). This replaces the
    coarse classical-CV blob/lane heuristic as the primary observation
    source for claim-consistency checking. ``client`` is injectable so
    tests can supply a mock and CI never spends API credits.
    """
    client = client or LLMClient()
    prompt = build_figure_vision_prompt(figure_label, figure_caption)
    obs = client.extract_json(
        prompt,
        schema=FIGURE_VISION_SCHEMA,
        system=FIGURE_VISION_SYSTEM,
        image_path=image_path,
    )
    return {**EMPTY_OBSERVATIONS, **obs}
